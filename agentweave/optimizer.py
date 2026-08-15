from __future__ import annotations
import itertools, math
from dataclasses import dataclass

@dataclass
class TeamObjective:
    coverage: float
    trust: float
    diversity: float
    redundancy: float
    latency: float
    cost: float
    communication: float
    score: float

class GlobalTeamOptimizer:
    """Exact subset search for small candidate pools, greedy approximation for large ones."""
    def __init__(self,exact_limit=18): self.exact_limit=exact_limit
    def evaluate(self,req,team):
        required=set(req.capabilities); covered=set(); trusts=[]; locations=set(); caps=[]; latency=0.0; cost=0.0
        for r in team:
            covered |= set(r.matched_capabilities); trusts.append(r.agent.trust.score()); locations.add(r.agent.execution.location); caps.append(set(r.matched_capabilities)); latency=max(latency,float(r.agent.execution.latency_ms)); cost+=float(r.agent.execution.cost)
        coverage=len(covered & required)/max(1,len(required)); trust=sum(trusts)/max(1,len(trusts)); diversity=min(1.0,len(locations)/max(1,len(team)))
        overlaps=[]
        for i in range(len(caps)):
            for j in range(i+1,len(caps)): overlaps.append(len(caps[i]&caps[j])/max(1,len(caps[i]|caps[j])))
        redundancy=sum(overlaps)/max(1,len(overlaps)); latency_score=1/(1+latency/1000); cost_score=1/(1+cost); communication_score=1/(1+max(0,len(team)-1)*.15)
        score=.42*coverage+.18*trust+.10*diversity+.10*(1-redundancy)+.08*latency_score+.07*cost_score+.05*communication_score
        return TeamObjective(coverage,trust,diversity,redundancy,latency_score,cost_score,communication_score,score)
    def select(self,req,ranked,max_agents=5):
        ranked=[r for r in ranked if r.score>0]
        if not ranked: return []
        if len(ranked)<=self.exact_limit:
            best=None; best_obj=None
            for n in range(1,min(max_agents,len(ranked))+1):
                for combo in itertools.combinations(ranked,n):
                    obj=self.evaluate(req,combo)
                    if best_obj is None or obj.score>best_obj.score: best,best_obj=list(combo),obj
            return best or []
        # scalable marginal-gain approximation
        selected=[]; pool=list(ranked); current=0.0
        while pool and len(selected)<max_agents:
            scored=[]
            for r in pool:
                obj=self.evaluate(req,selected+[r]); scored.append((obj.score-current,r,obj))
            gain,r,obj=max(scored,key=lambda x:x[0])
            if gain<=0 and selected: break
            selected.append(r); pool.remove(r); current=obj.score
            if obj.coverage>=1.0 and len(selected)>=2: break
        return selected
