from __future__ import annotations
import asyncio, json, time, uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
import httpx

@dataclass
class TaskState:
    task_id: str
    agent_id: str
    status: str='submitted'
    attempts: int=0
    result: dict|None=None
    error: str|None=None
    updated_at: float=field(default_factory=time.time)

class TaskStateStore:
    def __init__(self): self.tasks:dict[str,TaskState]={}
    def save(self,state:TaskState): state.updated_at=time.time(); self.tasks[state.task_id]=state; return state
    def get(self,task_id): return self.tasks.get(task_id)

class LongRunningA2AClient:
    """A2A v1 lifecycle client for JSON-RPC and HTTP+JSON.

    Covers SendMessage, SendStreamingMessage, SubscribeToTask, GetTask,
    ListTasks and CancelTask, with retry state and resumable polling.
    """
    def __init__(self,timeout=120,max_retries=3,backoff=1.0,state_store=None,protocol_version='1.0'):
        self.timeout=timeout; self.max_retries=max_retries; self.backoff=backoff; self.store=state_store or TaskStateStore(); self.protocol_version=protocol_version
    def _interface(self,agent):
        card=agent.metadata.get('agent_card',{}); interfaces=card.get('supportedInterfaces') or card.get('supported_interfaces') or []; iface=interfaces[0] if interfaces and isinstance(interfaces[0],dict) else {}
        endpoint=agent.execution.endpoint or iface.get('url') or card.get('url'); binding=str(agent.metadata.get('protocol_binding') or iface.get('protocolBinding') or 'JSONRPC').upper(); tenant=iface.get('tenant')
        if not endpoint: raise ValueError('agent endpoint missing')
        return endpoint.rstrip('/'),binding,tenant
    def _message(self,text,context=None,task_id=None):
        msg={'messageId':str(uuid.uuid4()),'role':'ROLE_USER','parts':[{'text':text}],'metadata':context or {}}
        if task_id: msg['taskId']=task_id
        return msg
    async def _rpc(self,endpoint,method,params,*,stream=False):
        payload={'jsonrpc':'2.0','id':str(uuid.uuid4()),'method':method,'params':params}; headers={'Content-Type':'application/json','A2A-Version':self.protocol_version}
        client=httpx.AsyncClient(timeout=None if stream else self.timeout,follow_redirects=True)
        if not stream:
            async with client:
                response=await client.post(endpoint,json=payload,headers=headers); response.raise_for_status(); data=response.json()
            if 'error' in data: raise RuntimeError(str(data['error']))
            return data.get('result',data)
        return client,payload,headers
    async def send(self,agent,message,context=None,task_id=None):
        endpoint,binding,tenant=self._interface(agent); local_id=task_id or str(uuid.uuid4()); state=self.store.save(TaskState(local_id,agent.agent_id)); msg=self._message(message,context,task_id)
        for attempt in range(self.max_retries+1):
            state.attempts=attempt+1; state.status='running'; self.store.save(state)
            try:
                if binding in {'HTTP+JSON','HTTP_JSON','REST'}:
                    payload={'message':msg};
                    if tenant: payload['tenant']=tenant
                    async with httpx.AsyncClient(timeout=self.timeout,follow_redirects=True) as client:
                        response=await client.post(endpoint+'/message:send',json=payload,headers={'Content-Type':'application/a2a+json','A2A-Version':self.protocol_version}); response.raise_for_status(); data=response.json()
                else:
                    params={'message':msg};
                    if tenant: params['tenant']=tenant
                    data=await self._rpc(endpoint,'SendMessage',params)
                remote_id=(data.get('id') if isinstance(data,dict) else None) or (data.get('task',{}).get('id') if isinstance(data,dict) else None) or local_id
                if remote_id!=state.task_id: self.store.tasks.pop(state.task_id,None); state.task_id=str(remote_id)
                state.status=self._status(data) or 'completed'; state.result=data; state.error=None; self.store.save(state); return state
            except Exception as exc:
                state.error=str(exc); self.store.save(state)
                if attempt>=self.max_retries: state.status='failed'; self.store.save(state); return state
                await asyncio.sleep(self.backoff*(2**attempt))
    async def stream(self,agent,message,context=None,task_id=None)->AsyncIterator[dict]:
        endpoint,binding,tenant=self._interface(agent); msg=self._message(message,context,task_id)
        if binding in {'HTTP+JSON','HTTP_JSON','REST'}:
            url=endpoint+'/message:stream'; payload={'message':msg}; headers={'Accept':'text/event-stream','Content-Type':'application/a2a+json','A2A-Version':self.protocol_version}
            if tenant: payload['tenant']=tenant
        else:
            url=endpoint; params={'message':msg};
            if tenant: params['tenant']=tenant
            payload={'jsonrpc':'2.0','id':str(uuid.uuid4()),'method':'SendStreamingMessage','params':params}; headers={'Accept':'text/event-stream','Content-Type':'application/json','A2A-Version':self.protocol_version}
        async for data in self._sse(url,payload,headers,method='POST'): yield data
    async def subscribe(self,agent,task_id)->AsyncIterator[dict]:
        endpoint,binding,tenant=self._interface(agent)
        if binding in {'HTTP+JSON','HTTP_JSON','REST'}:
            url=endpoint+'/tasks/'+task_id+':subscribe'; payload=None; headers={'Accept':'text/event-stream','A2A-Version':self.protocol_version}
            async for data in self._sse(url,payload,headers,method='GET'): yield data
        else:
            params={'id':task_id};
            if tenant: params['tenant']=tenant
            payload={'jsonrpc':'2.0','id':str(uuid.uuid4()),'method':'SubscribeToTask','params':params}; headers={'Accept':'text/event-stream','Content-Type':'application/json','A2A-Version':self.protocol_version}
            async for data in self._sse(endpoint,payload,headers,method='POST'): yield data
    async def _sse(self,url,payload,headers,method='POST'):
        async with httpx.AsyncClient(timeout=None,follow_redirects=True) as client:
            kwargs={'headers':headers}
            if payload is not None: kwargs['json']=payload
            async with client.stream(method,url,**kwargs) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or line.startswith(':') or line.startswith('event:'): continue
                    raw=line[5:].strip() if line.startswith('data:') else line
                    try:
                        data=json.loads(raw)
                        if isinstance(data,dict) and 'result' in data: data=data['result']
                        yield data
                    except json.JSONDecodeError: yield {'data':raw}
    async def get_task(self,agent,task_id,history_length=None):
        endpoint,binding,tenant=self._interface(agent)
        if binding in {'HTTP+JSON','HTTP_JSON','REST'}:
            params={} if history_length is None else {'historyLength':history_length}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response=await client.get(endpoint+'/tasks/'+task_id,params=params,headers={'A2A-Version':self.protocol_version}); response.raise_for_status(); return response.json()
        params={'id':task_id};
        if history_length is not None: params['historyLength']=history_length
        if tenant: params['tenant']=tenant
        return await self._rpc(endpoint,'GetTask',params)
    async def list_tasks(self,agent,**filters):
        endpoint,binding,tenant=self._interface(agent)
        if tenant: filters.setdefault('tenant',tenant)
        if binding in {'HTTP+JSON','HTTP_JSON','REST'}:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response=await client.get(endpoint+'/tasks',params=filters,headers={'A2A-Version':self.protocol_version}); response.raise_for_status(); return response.json()
        return await self._rpc(endpoint,'ListTasks',filters)
    async def cancel(self,agent,task_id):
        endpoint,binding,tenant=self._interface(agent)
        if binding in {'HTTP+JSON','HTTP_JSON','REST'}:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response=await client.post(endpoint+'/tasks/'+task_id+':cancel',headers={'Content-Type':'application/a2a+json','A2A-Version':self.protocol_version}); response.raise_for_status(); data=response.json()
        else:
            params={'id':task_id};
            if tenant: params['tenant']=tenant
            data=await self._rpc(endpoint,'CancelTask',params)
        state=self.store.get(task_id)
        if state: state.status='cancelled'; state.result=data; self.store.save(state)
        return data
    async def resume(self,agent,task_id,poll_interval=.5,timeout=None):
        deadline=time.monotonic()+(timeout or self.timeout)
        while True:
            data=await self.get_task(agent,task_id); status=self._status(data); state=self.store.get(task_id)
            if state: state.result=data; state.status=status or state.status; self.store.save(state)
            if status in {'completed','failed','canceled','cancelled','rejected'} or time.monotonic()>=deadline: return data
            await asyncio.sleep(poll_interval)
    @staticmethod
    def _status(data:Any):
        if not isinstance(data,dict): return None
        status=data.get('status')
        if isinstance(status,dict): status=status.get('state')
        if status is None and isinstance(data.get('task'),dict): return LongRunningA2AClient._status(data['task'])
        if status is None: return None
        return str(status).lower().replace('task_state_','')
