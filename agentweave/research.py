from __future__ import annotations
import random, statistics, time
from dataclasses import dataclass

@dataclass
class EvaluationRow:
    case_id: int
    method: str
    coverage: float
    mean_score: float
    trust: float
    latency_ms: float
    cost: float
    team_size: int

class ResearchBenchmark:
    """Reproducible routing baselines and ablations for AgentWeave."""
    def __init__(self,seed=41): self.rng=random.Random(seed)
    def _metrics(self,req,team,method,case_id):
        required=set(req.capabilities); covered=set(); scores=[]; trusts=[]; latency=0.; cost=0.
        for r in team:
            covered|=set(r.matched_capabilities); scores.append(float(r.score)); trusts.append(r.agent.trust.score())
            latency=max(latency,float(r.agent.execution.latency_ms)); cost+=float(r.agent.execution.cost)
        return EvaluationRow(case_id,method,len(covered&required)/max(1,len(required)),statistics.mean(scores) if scores else 0.,statistics.mean(trusts) if trusts else 0.,latency,cost,len(team))
    def evaluate(self,weave,cases,max_agents=5):
        rows=[]
        for idx,text in enumerate(cases):
            req=weave.analyzer.analyze(text); ranked=weave.matcher.rank(req,weave.registry.all()); selected=weave.selector.select(req,ranked,max_agents=max_agents)
            rows.append(self._metrics(req,selected,'agentweave',idx)); rows.append(self._metrics(req,ranked[:1],'single-best',idx))
            k=max(1,len(selected)); random_team=self.rng.sample(ranked,min(k,len(ranked))) if ranked else []
            rows.append(self._metrics(req,random_team,'random',idx))
            rows.append(self._metrics(req,sorted(ranked,key=lambda r:r.agent.trust.score(),reverse=True)[:k],'trust-only',idx))
            uncovered=set(req.capabilities); greedy=[]
            for r in ranked:
                if r.matched_capabilities & uncovered: greedy.append(r); uncovered-=r.matched_capabilities
                if not uncovered or len(greedy)>=max_agents: break
            rows.append(self._metrics(req,greedy,'capability-greedy',idx))
            rows.append(self._metrics(req,sorted(ranked,key=lambda r:.84*r.score-.16*r.agent.trust.score(),reverse=True)[:k],'ablation-no-trust',idx))
            rows.append(self._metrics(req,sorted(ranked,key=lambda r:.90*r.score-.10*r.placement_score,reverse=True)[:k],'ablation-no-placement',idx))
        return rows
    @staticmethod
    def aggregate(rows):
        groups={}
        for r in rows: groups.setdefault(r.method,[]).append(r)
        return {m:{k:statistics.mean(getattr(x,k) for x in xs) for k in ('coverage','mean_score','trust','latency_ms','cost','team_size')} for m,xs in groups.items()}
    def bootstrap_delta(self,rows,metric='coverage',baseline='single-best',iterations=2000):
        aw=[r for r in rows if r.method=='agentweave']; paired={r.case_id:r for r in rows if r.method==baseline}
        deltas=[getattr(r,metric)-getattr(paired[r.case_id],metric) for r in aw if r.case_id in paired]
        if not deltas: return {'mean_delta':0.,'ci95':[0.,0.]}
        samples=sorted(statistics.mean(self.rng.choice(deltas) for _ in deltas) for _ in range(iterations))
        return {'mean_delta':statistics.mean(deltas),'ci95':[samples[int(.025*len(samples))],samples[min(len(samples)-1,int(.975*len(samples)))]]}

class ScaleSuite:
    """Physical 10K/100K/1M matcher benchmark with bounded memory batching."""
    def __init__(self,factory,batch_size=25_000): self.factory=factory; self.batch_size=batch_size
    def run(self,weave,sizes=(10_000,100_000,1_000_000),seed=7):
        req=weave.analyzer.analyze('research analyze summarize verify and plan'); rows=[]
        native_obj=weave.matcher.native
        modes=['python']+(['native'] if weave.matcher.native_available else [])
        for n in sizes:
            for mode in modes:
                weave.matcher.native=native_obj if mode=='native' else None
                processed=0; top_score=None; elapsed=0.; batches=0
                while processed<n:
                    count=min(self.batch_size,n-processed); agents=self.factory.build(count,seed=seed+batches)
                    started=time.perf_counter(); ranked=weave.matcher.rank(req,agents); elapsed+=time.perf_counter()-started
                    if ranked: top_score=max(top_score if top_score is not None else ranked[0].score,ranked[0].score)
                    processed+=count; batches+=1
                rows.append({'agents':n,'mode':mode,'seconds':elapsed,'agents_per_second':n/max(elapsed,1e-12),'top_score':top_score,'batch_size':self.batch_size,'physical_agents_evaluated':processed})
        weave.matcher.native=native_obj
        return rows
