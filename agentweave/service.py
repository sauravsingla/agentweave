try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except ImportError as exc:
    raise RuntimeError("Install AgentWeave with the api extra: pip install -e .[api]") from exc

from .orchestrator import AgentWeave

app = FastAPI(title="AgentWeave", version="0.1.0")
engine = AgentWeave()

class SolveRequest(BaseModel):
    requirement: str
    domains: list[str] = []
    local_only: bool = False
    max_agents: int = 5

@app.get("/health")
def health():
    return {"status":"ok","agents":len(engine.registry.all())}

@app.post("/solve")
async def solve(req: SolveRequest):
    return await engine.solve(req.requirement, domains=req.domains, local_only=req.local_only, max_agents=req.max_agents)
