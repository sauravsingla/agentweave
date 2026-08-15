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
    """A2A 1.x transport with current message/send wire format and legacy fallback."""
    def __init__(self,headers=None,timeout=30,protocol_version='1.0'):
        self.headers=headers or {}; self.timeout=timeout; self.protocol_version=protocol_version

    def _message(self,task,context=None):
        return {
            'kind':'message',
            'messageId':str(uuid.uuid4()),
            'role':'user',
            'parts':[{'kind':'text','text':task}],
            'metadata':context or {},
        }

    def _legacy_message(self,task,context=None):
        return {
            'messageId':str(uuid.uuid4()),
            'role':'ROLE_USER',
            'parts':[{'text':task}],
            'metadata':context or {},
        }

    @staticmethod
    def _result_or_raise(data):
        if 'error' in data: raise RuntimeError(str(data['error']))
        return data.get('result',data)

    async def invoke(self,agent,task,context=None):
        card=agent.metadata.get('agent_card',{}); endpoint=agent.execution.endpoint or card.get('url')
        if not endpoint: raise ValueError('Agent has no A2A endpoint')
        binding=str(agent.metadata.get('protocol_binding') or card.get('protocolBinding') or 'JSONRPC').upper()
        headers={'A2A-Version':self.protocol_version,**self.headers}
        async with httpx.AsyncClient(timeout=self.timeout,follow_redirects=True) as client:
            if binding in {'HTTP+JSON','REST','HTTP_JSON'}:
                url=endpoint.rstrip('/')+'/message:send' if not endpoint.rstrip('/').endswith('/message:send') else endpoint
                r=await client.post(url,json={'message':self._message(task,context)},headers={'Content-Type':'application/json',**headers})
                r.raise_for_status(); return r.json()

            request_id=str(uuid.uuid4())
            current={
                'jsonrpc':'2.0',
                'id':request_id,
                'method':'message/send',
                'params':{'message':self._message(task,context),'metadata':context or {}},
            }
            r=await client.post(endpoint,json=current,headers={'Content-Type':'application/json',**headers})
            r.raise_for_status(); data=r.json()
            if 'error' not in data:
                return data.get('result',data)

            # Some pre-1.0 SDK samples still expose the historical SendMessage name.
            # Retry only for method/parameter/format compatibility errors; do not hide
            # application failures from a current A2A server.
            err=data.get('error') or {}; code=err.get('code') if isinstance(err,dict) else None
            if code not in {-32601,-32602,-32005}:
                raise RuntimeError(str(err))
            legacy={
                'jsonrpc':'2.0',
                'id':str(uuid.uuid4()),
                'method':'SendMessage',
                'params':{'message':self._legacy_message(task,context),'metadata':context or {}},
            }
            r=await client.post(endpoint,json=legacy,headers={'Content-Type':'application/json',**headers})
            r.raise_for_status(); return self._result_or_raise(r.json())
