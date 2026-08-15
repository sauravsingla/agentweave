from __future__ import annotations
import asyncio, json, os, pathlib, subprocess, sys, tempfile, time
from dataclasses import dataclass, asdict
from typing import Any
import httpx
from .a2a import HttpA2AAdapter
from .discovery import AgentCardDiscovery

@dataclass
class InteropTarget:
    name: str
    agent_card_url: str
    implementation: str = 'unknown'
    expected_transport: str | None = None

@dataclass
class InteropResult:
    target: str
    implementation: str
    discovered: bool
    invoked: bool
    latency_ms: float | None = None
    error: str | None = None
    agent_name: str | None = None
    transport: str | None = None

class A2AInteropSuite:
    """Runs live discovery/invocation checks against independent A2A endpoints."""
    def __init__(self, adapter=None):
        self.discovery=AgentCardDiscovery(); self.adapter=adapter or HttpA2AAdapter()
    async def run_target(self,target:InteropTarget,prompt='Return a short interoperability acknowledgement.'):
        started=time.perf_counter()
        try:
            agent=await self.discovery.fetch(target.agent_card_url)
            card=agent.metadata.get('agent_card',{})
            transport=str(agent.metadata.get('protocol_binding') or card.get('protocolBinding') or card.get('preferredTransport') or 'JSONRPC')
            response=await self.adapter.invoke(agent,prompt,context={'test':'agentweave-interop','implementation':target.implementation})
            return InteropResult(target.name,target.implementation,True,True,(time.perf_counter()-started)*1000,None,agent.name,transport)
        except Exception as exc:
            return InteropResult(target.name,target.implementation,False,False,(time.perf_counter()-started)*1000,str(exc))
    async def run(self,targets:list[InteropTarget],prompt=None):
        return await asyncio.gather(*(self.run_target(t,prompt or 'A2A interoperability test') for t in targets))
    @staticmethod
    def from_env(name='AGENTWEAVE_A2A_TARGETS'):
        raw=os.getenv(name,'').strip()
        if not raw: return []
        data=json.loads(raw)
        return [InteropTarget(**x) for x in data]

class A2ATCKRunner:
    """Integration wrapper for the Linux Foundation A2A Technology Compatibility Kit."""
    def __init__(self,tck_dir:str|None=None): self.tck_dir=tck_dir
    def run(self,sut_host:str,transport:str|None=None,level:str='must',timeout=300):
        if not self.tck_dir: raise ValueError('tck_dir is required; clone a2aproject/a2a-tck first')
        script=pathlib.Path(self.tck_dir)/'run_tck.py'
        if not script.exists(): raise FileNotFoundError(script)
        cmd=[sys.executable,str(script),'--sut-host',sut_host,'--level',level]
        if transport: cmd += ['--transport',transport]
        proc=subprocess.run(cmd,cwd=self.tck_dir,text=True,capture_output=True,timeout=timeout)
        return {'passed':proc.returncode==0,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr}

async def probe_well_known(base_url:str):
    url=base_url.rstrip('/')+'/.well-known/agent-card.json'
    async with httpx.AsyncClient(timeout=15,follow_redirects=True) as client:
        r=await client.get(url); r.raise_for_status(); return r.json()
