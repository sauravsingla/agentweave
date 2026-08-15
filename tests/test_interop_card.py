import pytest
from agentweave.discovery import AgentCardDiscovery

class FakeResponse:
    def raise_for_status(self): pass
    def json(self):
        return {
            'name':'Hello World Agent',
            'version':'1.0.0',
            'capabilities':{'streaming':True},
            'supportedInterfaces':[{'url':'http://127.0.0.1:9999/','protocolBinding':'JSONRPC','protocolVersion':'1.0'}],
            'skills':[{'id':'echo_bot','name':'Echo Bot'}],
        }

class FakeClient:
    async def __aenter__(self): return self
    async def __aexit__(self,*args): return False
    async def get(self,url): return FakeResponse()

@pytest.mark.asyncio
async def test_discovery_parses_a2a_v1_supported_interfaces(monkeypatch):
    monkeypatch.setattr('agentweave.discovery.httpx.AsyncClient',lambda **kwargs:FakeClient())
    agent=await AgentCardDiscovery().fetch('http://host/.well-known/agent-card.json')
    assert agent.execution.endpoint=='http://127.0.0.1:9999/'
    assert agent.metadata['protocol_binding']=='JSONRPC'
    assert agent.metadata['protocol_version']=='1.0'
    assert agent.metadata['streaming'] is True
    assert agent.capabilities[0].name=='echo_bot'
