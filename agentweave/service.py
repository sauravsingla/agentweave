from __future__ import annotations
from .orchestrator import AgentWeave

def create_app(weave:AgentWeave|None=None):
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel
    except ImportError as e:
        raise RuntimeError("Install agentweave[api]") from e
    app=FastAPI(title='AgentWeave',version='0.2.0'); engine=weave or AgentWeave()
    class SolveRequest(BaseModel):
        text:str
        domains:list[str]|None=None
        knowledge:list[str]|None=None
        local_only:bool=False
        max_agents:int=5
        rounds:int=2
    @app.get('/health')
    async def health(): return {'status':'ok','agents':len(engine.registry.all())}
    @app.post('/solve')
    async def solve(req:SolveRequest):
        return await engine.solve(req.text,domains=req.domains,knowledge=req.knowledge,local_only=req.local_only,max_agents=req.max_agents,rounds=req.rounds)
    return app
