from __future__ import annotations
from .models import MatchResult

class NativeAcceleration:
    """Optional bridge to the pybind11 C++ core with safe Python fallback."""
    def __init__(self):
        try: import _agentweave_core as core
        except Exception: core=None
        self.core=core
    @property
    def available(self)->bool: return self.core is not None
    def rank(self,req,agents,trust_engine,placement_engine):
        if not self.core: return None
        candidates=[]; by_id={}
        for a in agents:
            placement=placement_engine.score(req,a)
            if placement<=0: continue
            c=self.core.Candidate(); c.id=a.agent_id; c.capabilities=[x.name.lower() for x in a.capabilities]
            c.proficiency=sum(x.proficiency for x in a.capabilities)/max(1,len(a.capabilities)); c.trust=trust_engine.score(a); c.placement=placement
            candidates.append(c); by_id[a.agent_id]=a
        ranked=self.core.rank(sorted(req.capabilities),candidates); out=[]
        for r in ranked:
            a=by_id[r.id]; matched=set(r.matched); missing=set(req.capabilities)-matched; p=placement_engine.score(req,a)
            out.append(MatchResult(a,float(r.score),matched,missing,p))
        return out
