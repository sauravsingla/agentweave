from __future__ import annotations
import asyncio, uuid, httpx
from typing import Any, Awaitable, Callable
from .models import AgentProfile

Handler=Callable[[str],Any|Awaitable[Any]]

class A2AAdapter:
    async def invoke(self,agent:AgentProfile,task:str,context:dict|None=None)->dict: raise NotImplementedError

class InMemoryA2AAdapter(A2AAdapter):
    def __init__(self): self.handlers={}
    def register_handler(self,agent_id,handler:Handler): self.handlers[agent_id]=handler
    async def invoke(self,agent,task,context=None):
        if agent.agent_id not in self.handlers: raise KeyError(f'No handler for {agent.agent_id}')
        r=self.handlers[agent.agent_id](task)
        if asyncio.iscoroutine(r): r=await r
        return r if isinstance(r,dict) else {'result':r}

class HttpA2AAdapter(A2AAdapter):
    """A2A transport with binding/version negotiation and legacy wire compatibility."""
    COMPAT_CODES={-32601,-32602,-32005}

    def __init__(self,headers=None,timeout=30,protocol_version='1.0'):
        self.headers=headers or {}; self.timeout=timeout; self.protocol_version=protocol_version

    def _message(self,task,context=None):
        return {'kind':'message','messageId':str(uuid.uuid4()),'role':'user','parts':[{'kind':'text','text':task}],'metadata':context or {}}

    def _legacy_message(self,task,context=None):
        return {'messageId':str(uuid.uuid4()),'role':'ROLE_USER','parts':[{'text':task}],'metadata':context or {}}

    @staticmethod
    def _result_or_raise(data):
        if 'error' in data: raise RuntimeError(str(data['error']))
        return data.get('result',data)

    @staticmethod
    def _error_code(data):
        err=data.get('error') if isinstance(data,dict) else None
        return err.get('code') if isinstance(err,dict) else None

    async def _post_rpc(self,client,endpoint,method,message,headers,context=None):
        payload={'jsonrpc':'2.0','id':str(uuid.uuid4()),'method':method,'params':{'message':message}}
        if context:
            payload['params']['metadata']=context
        r=await client.post(endpoint,json=payload,headers={'Content-Type':'application/json',**headers})
        r.raise_for_status()
        return r.json()

    async def invoke_message(self,agent,message:dict,rpc_method:str|None=None,context:dict|None=None,content_type:str|None=None):
        card=agent.metadata.get('agent_card',{}); endpoint=agent.execution.endpoint or card.get('url')
        if not endpoint: raise ValueError('Agent has no A2A endpoint')
        binding=str(agent.metadata.get('protocol_binding') or card.get('protocolBinding') or card.get('preferredTransport') or 'JSONRPC').upper()
        version=str(agent.metadata.get('protocol_version') or card.get('protocolVersion') or self.protocol_version)
        headers={'A2A-Version':version,**self.headers}
        async with httpx.AsyncClient(timeout=self.timeout,follow_redirects=True) as client:
            if binding in {'HTTP+JSON','REST','HTTP_JSON'}:
                url=endpoint.rstrip('/')+'/message:send' if not endpoint.rstrip('/').endswith('/message:send') else endpoint
                r=await client.post(url,json={'message':message},headers={'Content-Type':content_type or 'application/a2a+json',**headers})
                r.raise_for_status(); data=r.json()
                if isinstance(data,dict) and 'error' in data: raise RuntimeError(str(data['error']))
                return data
            method=rpc_method or 'message/send'
            data=await self._post_rpc(client,endpoint,method,message,headers,context)
            return self._result_or_raise(data)

    async def invoke(self,agent,task,context=None):
        card=agent.metadata.get('agent_card',{}); endpoint=agent.execution.endpoint or card.get('url')
        if not endpoint: raise ValueError('Agent has no A2A endpoint')
        binding=str(agent.metadata.get('protocol_binding') or card.get('protocolBinding') or card.get('preferredTransport') or 'JSONRPC').upper()
        version=str(agent.metadata.get('protocol_version') or card.get('protocolVersion') or self.protocol_version)
        headers={'A2A-Version':version,**self.headers}
        async with httpx.AsyncClient(timeout=self.timeout,follow_redirects=True) as client:
            if binding in {'HTTP+JSON','REST','HTTP_JSON'}:
                url=endpoint.rstrip('/')+'/message:send' if not endpoint.rstrip('/').endswith('/message:send') else endpoint
                r=await client.post(url,json={'message':self._message(task,context)},headers={'Content-Type':'application/a2a+json',**headers})
                r.raise_for_status(); data=r.json()
                if isinstance(data,dict) and 'error' in data: raise RuntimeError(str(data['error']))
                return data

            attempts=[
                ('message/send',self._message(task,context),'current'),
                ('message/send',self._legacy_message(task,context),'legacy-message'),
                ('SendMessage',self._legacy_message(task,context),'legacy-method'),
            ]
            errors=[]
            for method,message,label in attempts:
                data=await self._post_rpc(client,endpoint,method,message,headers,context)
                if 'error' not in data:
                    return data.get('result',data)
                err=data.get('error') or {}; errors.append({'profile':label,'error':err})
                if self._error_code(data) not in self.COMPAT_CODES:
                    raise RuntimeError(str(err))
            raise RuntimeError(str({'message':'No compatible A2A wire profile succeeded','attempts':errors}))
