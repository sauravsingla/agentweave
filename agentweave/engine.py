from __future__ import annotations
from .models import AgentProfile, MatchResult
from .native import NativeAcceleration

class AgentRegistry:
    def __init__(self,store=None,graph=None): self._agents={}; self.store=store; self.graph=graph
    def register(self,a:AgentProfile):
        self._agents[a.agent_id]=a
        if self.graph: self.graph.add_agent(a)
        if self.store: self.store.save_agent(a)
        return a
    def all(self): return list(self._agents.values())
    def get(self,agent_id): return self._agents.get(agent_id)
    def load_persisted(self):
        if self.store:
            for a in self.store.load_agents(): self.register(a)
        return len(self._agents)

class TrustEngine:
    def __init__(self,store=None): self.store=store
    def score(self,a):
        history=a.tasks_succeeded/a.tasks_completed if a.tasks_completed else a.trust.historical
        return .85*a.trust.score()+.15*history
    def update(self,a,success,quality_score=0.0,detail=None):
        a.tasks_completed+=1; a.tasks_succeeded+=int(bool(success)); obs=max(0.0,min(1.0,float(quality_score if success else 0.0)))
        a.trust.historical=.8*a.trust.historical+.2*obs
        if self.store: self.store.record_outcome(a.agent_id,success,quality_score,detail); self.store.save_agent(a)

class PlacementEngine:
    def score(self,req,a):
        if not a.execution.available: return 0.0
        if req.local_only and a.execution.location!='edge': return 0.0
        if req.max_latency_ms is not None and a.execution.latency_ms>req.max_latency_ms: return 0.0
        if getattr(req,'privacy_level',None)=='local-only' and a.execution.location!='edge': return 0.0
        locality=1.0 if a.execution.location=='edge' else .75
        privacy=1.0 if a.execution.privacy_level in {'local-only','confidential'} else .65
        latency=1/(1+a.execution.latency_ms/1000)
        cost=1/(1+max(0.0,float(getattr(a.execution,'cost',0.0))))
        return .31*locality+.31*privacy+.25*latency+.13*cost

class AgentMatcher:
    def __init__(self,trust,placement,use_native=True): self.trust=trust; self.placement=placement; self.native=NativeAcceleration() if use_native else None
    @property
    def native_available(self): return bool(self.native and self.native.available)
    def match(self,req,a):
        cmap={c.name.lower():c for c in a.capabilities}; matched=req.capabilities & set(cmap); missing=req.capabilities-set(cmap)
        p=self.placement.score(req,a)
        if p<=0: return MatchResult(a,0.0,matched,missing,0.0)
        coverage=len(matched)/max(1,len(req.capabilities)); prof=sum(cmap[c].proficiency for c in matched)/len(matched) if matched else 0.0
        valid=sum(1 for c in matched if cmap[c].validated)/len(matched) if matched else 0.0
        domain=1.0 if not req.domains or req.domains & set(map(str.lower,a.domains)) else .25
        knowledge=1.0 if not req.knowledge or req.knowledge & set(map(str.lower,a.knowledge)) else .35
        score=.30*coverage+.17*prof+.10*valid+.16*self.trust.score(a)+.09*domain+.08*knowledge+.10*p
        return MatchResult(a,score,matched,missing,p)
    def rank(self,req,agents):
        agents=list(agents)
        if self.native_available:
            out=self.native.rank(req,agents,self.trust,self.placement)
            if out is not None: return out
        return sorted((self.match(req,a) for a in agents),key=lambda x:x.score,reverse=True)

class TeamSelector:
    def select(self,req,ranked,max_agents=5):
        uncovered=set(req.capabilities); team=[]; pool=[r for r in ranked if r.score>0]
        while uncovered and pool and len(team)<max_agents:
            best=max(pool,key=lambda r:(len(r.matched_capabilities & uncovered),r.score))
            new=best.matched_capabilities & uncovered
            if not new: break
            team.append(best); uncovered-=new; pool.remove(best)
        if not team and pool: team=[pool[0]]
        return team
