from __future__ import annotations
import asyncio, json, shutil
from .models import AgentProfile

class EdgeRuntime:
    async def invoke(self,agent:AgentProfile,prompt:str)->dict: raise NotImplementedError

class LlamaCppRuntime(EdgeRuntime):
    def __init__(self,binary='llama-cli'): self.binary=binary
    async def invoke(self,agent,prompt):
        model=agent.metadata.get('model_path')
        if not model: raise ValueError('model_path missing')
        if not shutil.which(self.binary): raise RuntimeError(f'{self.binary} not installed')
        proc=await asyncio.create_subprocess_exec(self.binary,'-m',model,'-p',prompt,'-n',str(agent.metadata.get('max_tokens',256)),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        out,err=await proc.communicate()
        if proc.returncode: raise RuntimeError(err.decode(errors='ignore'))
        return {'result':out.decode(errors='ignore'),'runtime':'llama.cpp'}

class OllamaRuntime(EdgeRuntime):
    def __init__(self,base_url='http://127.0.0.1:11434'): self.base_url=base_url
    async def invoke(self,agent,prompt):
        import httpx
        model=agent.metadata.get('model')
        if not model: raise ValueError('model missing')
        async with httpx.AsyncClient(timeout=120) as client:
            r=await client.post(f'{self.base_url}/api/generate',json={'model':model,'prompt':prompt,'stream':False}); r.raise_for_status(); data=r.json()
        return {'result':data.get('response',''),'runtime':'ollama'}

class EdgeA2AAdapter:
    def __init__(self,default_runtime=None): self.default_runtime=default_runtime or OllamaRuntime(); self.runtimes={}
    def register_runtime(self,agent_id,runtime): self.runtimes[agent_id]=runtime
    async def invoke(self,agent,task,context=None): return await self.runtimes.get(agent.agent_id,self.default_runtime).invoke(agent,task)
