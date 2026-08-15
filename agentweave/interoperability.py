from __future__ import annotations
import asyncio, json, os, pathlib, subprocess, sys, time
from dataclasses import dataclass
import httpx
from .a2a import HttpA2AAdapter
from .discovery import AgentCardDiscovery

@dataclass
class InteropTarget:
    name: str
    agent_card_url: str
    implementation: str='unknown'
    expected_transport: str|None=None
    rpc_method: str|None=None
    message: dict|None=None
    content_type: str|None=None
    params: dict|None=None
    headers: dict|None=None
    bootstrap: dict|None=None
    http_bootstrap: dict|None=None

@dataclass
class InteropResult:
    target: str
    implementation: str
    discovered: bool
    invoked: bool
    latency_ms: float|None=None
    error: str|None=None
    agent_name: str|None=None
    transport: str|None=None
    streaming_advertised: bool=False


def _dig(obj,path):
    cur=obj
    for part in str(path).split('.'):
        if not isinstance(cur,dict) or part not in cur: return None
        cur=cur[part]
    return cur


def _find_key(obj,names):
    wanted={str(x).lower() for x in names}
    if isinstance(obj,dict):
        for k,v in obj.items():
            if str(k).lower() in wanted and isinstance(v,(str,int,float)) and str(v): return v
        for v in obj.values():
            found=_find_key(v,wanted)
            if found is not None: return found
    elif isinstance(obj,list):
        for v in obj:
            found=_find_key(v,wanted)
            if found is not None: return found
    return None


def _capture_value(obj,spec):
    candidates=spec if isinstance(spec,list) else [spec]
    for path in candidates:
        value=_dig(obj,path)
        if value is not None: return value
    leaf_names=[str(x).split('.')[-1] for x in candidates]
    return _find_key(obj,leaf_names)

class A2AInteropSuite:
    def __init__(self,adapter=None): self.discovery=AgentCardDiscovery(); self.adapter=adapter or HttpA2AAdapter()

    async def _http_bootstrap(self,target,runtime_headers):
        boot=target.http_bootstrap or {}
        method=str(boot.get('method','POST')).upper(); url=boot['url']; body=boot.get('json')
        async with httpx.AsyncClient(timeout=30,follow_redirects=True) as client:
            r=await client.request(method,url,json=body,headers={'Content-Type':'application/json',**(boot.get('headers') or {})})
            r.raise_for_status(); data=r.json()
        for header,spec in (boot.get('capture_headers') or {}).items():
            value=_capture_value(data,spec)
            if value is None:
                raise RuntimeError(f'HTTP bootstrap response missing required credential for {header}')
            runtime_headers[header]=str(value)

    async def run_target(self,target:InteropTarget,prompt='A2A interoperability test'):
        started=time.perf_counter(); agent=None
        try:
            agent=await self.discovery.fetch(target.agent_card_url)
        except Exception as exc:
            return InteropResult(target.name,target.implementation,False,False,(time.perf_counter()-started)*1000,str(exc))
        transport=str(agent.metadata.get('protocol_binding') or 'JSONRPC')
        try:
            runtime_headers=dict(target.headers or {})
            if target.http_bootstrap:
                await self._http_bootstrap(target,runtime_headers)
            if target.bootstrap:
                boot=target.bootstrap
                result=await self.adapter.rpc_call(agent,boot['method'],boot.get('params') or {},extra_headers=runtime_headers)
                for header,spec in (boot.get('capture_headers') or {}).items():
                    value=_capture_value(result,spec)
                    if value is None: raise RuntimeError(f'Bootstrap response missing required credential for {header}')
                    runtime_headers[header]=str(value)
            if target.message is not None:
                await self.adapter.invoke_message(agent,target.message,rpc_method=target.rpc_method,context={'test':'agentweave-interop','implementation':target.implementation},content_type=target.content_type,extra_params=target.params,extra_headers=runtime_headers)
            else:
                await self.adapter.invoke(agent,prompt,context={'test':'agentweave-interop','implementation':target.implementation})
            return InteropResult(target.name,target.implementation,True,True,(time.perf_counter()-started)*1000,None,agent.name,transport,bool(agent.metadata.get('streaming')))
        except Exception as exc:
            return InteropResult(target.name,target.implementation,True,False,(time.perf_counter()-started)*1000,str(exc),agent.name,transport,bool(agent.metadata.get('streaming')))
    async def run(self,targets:list[InteropTarget],prompt=None):
        return await asyncio.gather(*(self.run_target(t,prompt or 'A2A interoperability test') for t in targets))
    @staticmethod
    def from_env(name='AGENTWEAVE_A2A_TARGETS'):
        raw=os.getenv(name,'').strip()
        if not raw: return []
        return [InteropTarget(**x) for x in json.loads(raw)]

class A2ATCKRunner:
    def __init__(self,tck_dir:str|None=None): self.tck_dir=tck_dir
    def run(self,sut_host:str,transport:str|None=None,level:str='must',timeout=300):
        if not self.tck_dir: raise ValueError('tck_dir is required')
        script=pathlib.Path(self.tck_dir)/'run_tck.py'
        cmd=[sys.executable,str(script),'--sut-host',sut_host,'--level',level]
        if transport: cmd += ['--transport',transport]
        proc=subprocess.run(cmd,cwd=self.tck_dir,text=True,capture_output=True,timeout=timeout)
        return {'passed':proc.returncode==0,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr}

async def probe_well_known(base_url:str):
    url=base_url.rstrip('/')+'/.well-known/agent-card.json'
    async with httpx.AsyncClient(timeout=15,follow_redirects=True) as client:
        r=await client.get(url); r.raise_for_status(); return r.json()
