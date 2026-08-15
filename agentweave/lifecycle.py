from __future__ import annotations
import asyncio, json, time, uuid
from dataclasses import dataclass, field
import httpx

@dataclass
class TaskState:
    task_id:str
    agent_id:str
    status:str='submitted'
    attempts:int=0
    result:dict|None=None
    error:str|None=None
    updated_at:float=field(default_factory=time.time)

class TaskStateStore:
    def __init__(self): self.tasks={}
    def save(self,state:TaskState): state.updated_at=time.time(); self.tasks[state.task_id]=state; return state
    def get(self,task_id): return self.tasks.get(task_id)

class LongRunningA2AClient:
    """Streaming/retry/cancel/resume lifecycle wrapper for A2A HTTP endpoints."""
    def __init__(self,timeout=120,max_retries=3,backoff=1.0,state_store=None): self.timeout=timeout; self.max_retries=max_retries; self.backoff=backoff; self.store=state_store or TaskStateStore()
    async def send(self,agent,message,context=None):
        endpoint=agent.execution.endpoint
        if not endpoint: raise ValueError('agent endpoint missing')
        task_id=str(uuid.uuid4()); state=self.store.save(TaskState(task_id,agent.agent_id))
        payload={'message':{'messageId':str(uuid.uuid4()),'role':'ROLE_USER','parts':[{'text':message}],'metadata':context or {}},'metadata':{'clientTaskId':task_id}}
        async with httpx.AsyncClient(timeout=self.timeout,follow_redirects=True) as c:
            for attempt in range(self.max_retries+1):
                state.attempts=attempt+1; state.status='running'; self.store.save(state)
                try:
                    r=await c.post(endpoint.rstrip('/')+'/message:send',json=payload,headers={'Content-Type':'application/a2a+json'}); r.raise_for_status(); data=r.json(); state.status='completed'; state.result=data; self.store.save(state); return state
                except Exception as exc:
                    state.error=str(exc); self.store.save(state)
                    if attempt>=self.max_retries: state.status='failed'; self.store.save(state); return state
                    await asyncio.sleep(self.backoff*(2**attempt))
    async def stream(self,agent,message,context=None):
        endpoint=agent.execution.endpoint
        if not endpoint: raise ValueError('agent endpoint missing')
        payload={'message':{'messageId':str(uuid.uuid4()),'role':'ROLE_USER','parts':[{'text':message}],'metadata':context or {}}}
        async with httpx.AsyncClient(timeout=None,follow_redirects=True) as c:
            async with c.stream('POST',endpoint.rstrip('/')+'/message:stream',json=payload,headers={'Accept':'text/event-stream','Content-Type':'application/a2a+json'}) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line or line.startswith(':'): continue
                    data=line[5:].strip() if line.startswith('data:') else line
                    try: yield json.loads(data)
                    except json.JSONDecodeError: yield {'data':data}
    async def cancel(self,agent,task_id):
        endpoint=agent.execution.endpoint
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.post(endpoint.rstrip('/')+'/tasks/'+task_id+':cancel',headers={'Content-Type':'application/a2a+json'}); r.raise_for_status(); state=self.store.get(task_id)
            if state: state.status='cancelled'; self.store.save(state)
            return r.json()
    async def resume(self,agent,task_id):
        endpoint=agent.execution.endpoint
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.get(endpoint.rstrip('/')+'/tasks/'+task_id); r.raise_for_status(); data=r.json(); state=self.store.get(task_id)
            if state: state.result=data; state.status=str(data.get('status',state.status)); self.store.save(state)
            return data
