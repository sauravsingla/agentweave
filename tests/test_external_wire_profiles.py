import pytest
from agentweave.a2a import HttpA2AAdapter
from agentweave.models import AgentProfile, Capability, ExecutionProfile


class FakeResponse:
    def __init__(self, payload): self._payload=payload
    def raise_for_status(self): pass
    def json(self): return self._payload


class FakeClient:
    calls=[]
    async def __aenter__(self): return self
    async def __aexit__(self,*args): return False
    async def post(self,url,json=None,headers=None):
        self.calls.append((url,json,headers))
        method=(json or {}).get('method')
        message=((json or {}).get('params') or {}).get('message') or {}
        if method=='message/send' and message.get('role')=='user':
            return FakeResponse({'error':{'code':-32602,'message':'legacy role required'}})
        if method=='message/send' and message.get('role')=='ROLE_USER':
            return FakeResponse({'result':{'ok':True}})
        if method=='SendMessage':
            return FakeResponse({'result':{'ok':True}})
        return FakeResponse({'error':{'code':-32601,'message':'Method not found'}})


def _agent():
    return AgentProfile('x','X',[Capability('echo')],execution=ExecutionProfile(endpoint='https://example.test/a2a'),metadata={'protocol_binding':'JSONRPC','protocol_version':'1.0','agent_card':{}})


@pytest.mark.asyncio
async def test_jsonrpc_adapts_current_method_to_legacy_message_shape(monkeypatch):
    FakeClient.calls=[]
    monkeypatch.setattr('agentweave.a2a.httpx.AsyncClient',lambda **kwargs:FakeClient())
    out=await HttpA2AAdapter().invoke(_agent(),'hello')
    assert out['ok'] is True
    assert [c[1]['method'] for c in FakeClient.calls][:2]==['message/send','message/send']
    assert FakeClient.calls[1][1]['params']['message']['role']=='ROLE_USER'


@pytest.mark.asyncio
async def test_explicit_structured_message_and_method(monkeypatch):
    FakeClient.calls=[]
    monkeypatch.setattr('agentweave.a2a.httpx.AsyncClient',lambda **kwargs:FakeClient())
    message={'role':'ROLE_USER','messageId':'m1','parts':[{'mediaType':'application/json','data':{'skill':'search_public_research','query':'agent interoperability','limit':2}}]}
    out=await HttpA2AAdapter().invoke_message(_agent(),message,rpc_method='SendMessage')
    assert out['ok'] is True
    assert FakeClient.calls[0][1]['method']=='SendMessage'
    assert FakeClient.calls[0][1]['params']['message']==message
