from __future__ import annotations
from .models import MatchResult

class NativeAcceleration:
    """Optional bridge to the pybind11 C++ core.

    If the extension is unavailable, callers can fall back to the Python matcher.
    """
    def __init__(self):
        try:
            import _agentweave_core as core
        except Exception:
            core=None
        self.core=core

    @property
    def available(self)->bool:
        return self.core is not None

    def rank(self,req,agents,trust_engine,placement_engine):
        if not self.core: return None
        candidates=[]
        by_id={a.agent_id:a for a in agents}
        for a in agents:
            c=self.core.Candidate(); c.id=a.agent_id; c.capabilities=[x.name.lower() for x in a.capabilities]
            c.proficiency=sum(x.proficiency for x in a.capabilities)/max(1,len(a.capabilities))
            c.trust=trust_engine.score(a); c.placement=placement_engine.score(req,a)
            candidates.append(c)
        ranked=self.core.rank(sorted(req.capabilities),candidates)
        out=[]
        for r in ranked:
            a=by_id[r.id]; matched=set(r.matched); missing=set(req.capabilities)-matched
            out.append(MatchResult(a,float(r.score),matched,missing,placement_engine.score(req,a)))
        return out

    def select_team_ids(self,required,ranked,max_agents=5):
        if not self.core: return None
        native=[]
        for r in ranked:
            x=self.core.Ranked.__new__(self.core.Ranked)
            # Ranked is read-only in the current binding, so team selection is only
            # available when native rank() produced the objects. Keep Python fallback.
            return None
        return None
