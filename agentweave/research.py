from __future__ import annotations
import os, random, statistics, time
from dataclasses import dataclass
from .advanced_graph import AdvancedKnowledgeGraph
try:
    import resource
except ImportError:  # Windows
    resource=None

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
    redundancy: float = 0.0
    diversity: float = 0.0
    quality_proxy: float = 0.0

class ResearchBenchmark:
    """Reproducible routing baselines and ablations for AgentWeave."""
    def __init__(self,seed=41): self.rng=random.Random(seed); self.semantic=AdvancedKnowledgeGraph()
    def _metrics(self,req,team,method,case_id):
        required=set(req.capabilities); covered=set(); scores=[]; trusts=[]; latency=0.; cost=0.; locations=set(); capsets=[]
        for row in team:
            caps=set(row.matched_capabilities); covered|=caps; capsets.append(caps); scores.append(float(row.score)); trusts.append(row.agent.trust.score()); locations.add(row.agent.execution.location)
            latency=max(latency,float(row.agent.execution.latency_ms)); cost+=float(row.agent.execution.cost)
        overlaps=[]
        for i in range(len(capsets)):
            for j in range(i+1,len(capsets)): overlaps.append(len(capsets[i]&capsets[j])/max(1,len(capsets[i]|capsets[j])))
        coverage=len(covered&required)/max(1,len(required)); mean_score=statistics.mean(scores) if scores else 0.; trust=statistics.mean(trusts) if trusts else 0.; redundancy=statistics.mean(overlaps) if overlaps else 0.; diversity=min(1.0,len(locations)/max(1,len(team))) if team else 0.
        quality_proxy=coverage*(.55*mean_score+.30*trust+.15*(1-redundancy))
        return EvaluationRow(case_id,method,coverage,mean_score,trust,latency,cost,len(team),redundancy,diversity,quality_proxy)
    def _embedding_only(self,req,ranked,k):
        required=sorted(req.capabilities)
        def score(row):
            names=[c.name for c in row.agent.capabilities]
            if not names or not required: return 0.0
            return statistics.mean(max(self.semantic.semantic_similarity(r,name) for name in names) for r in required)
        return sorted(ranked,key=score,reverse=True)[:k]
    def evaluate(self,weave,cases,max_agents=5):
        rows=[]
        for idx,text in enumerate(cases):
            req=weave.analyzer.analyze(text); ranked=weave.matcher.rank(req,weave.registry.all()); selected=weave.selector.select(req,ranked,max_agents=max_agents); k=max(1,len(selected))
            rows.append(self._metrics(req,selected,'agentweave',idx)); rows.append(self._metrics(req,ranked[:1],'single-best',idx))
            random_team=self.rng.sample(ranked,min(k,len(ranked))) if ranked else []; rows.append(self._metrics(req,random_team,'random',idx))
            rows.append(self._metrics(req,sorted(ranked,key=lambda r:r.agent.trust.score(),reverse=True)[:k],'trust-only',idx))
            uncovered=set(req.capabilities); greedy=[]
            for row in ranked:
                if row.matched_capabilities&uncovered: greedy.append(row); uncovered-=row.matched_capabilities
                if not uncovered or len(greedy)>=max_agents: break
            rows.append(self._metrics(req,greedy,'capability-greedy',idx)); rows.append(self._metrics(req,self._embedding_only(req,ranked,k),'embedding-only',idx))
            rows.append(self._metrics(req,sorted(ranked,key=lambda r:.84*r.score-.16*r.agent.trust.score(),reverse=True)[:k],'ablation-no-trust',idx))
            rows.append(self._metrics(req,sorted(ranked,key=lambda r:.90*r.score-.10*r.placement_score,reverse=True)[:k],'ablation-no-placement',idx))
            if weave.matcher.native_available:
                native_team=weave.matcher.native.select_team(req,ranked,max_agents=max_agents) or []; rows.append(self._metrics(req,native_team,'native-greedy',idx))
        return rows
    @staticmethod
    def aggregate(rows):
        groups={}
        for row in rows: groups.setdefault(row.method,[]).append(row)
        metrics=('coverage','mean_score','trust','latency_ms','cost','team_size','redundancy','diversity','quality_proxy')
        return {method:{metric:statistics.mean(getattr(row,metric) for row in group) for metric in metrics} for method,group in groups.items()}
    def bootstrap_delta(self,rows,metric='coverage',baseline='single-best',iterations=2000):
        aw=[r for r in rows if r.method=='agentweave']; paired={r.case_id:r for r in rows if r.method==baseline}; deltas=[getattr(r,metric)-getattr(paired[r.case_id],metric) for r in aw if r.case_id in paired]
        if not deltas: return {'mean_delta':0.,'ci95':[0.,0.]}
        samples=sorted(statistics.mean(self.rng.choice(deltas) for _ in deltas) for _ in range(iterations)); return {'mean_delta':statistics.mean(deltas),'ci95':[samples[int(.025*len(samples))],samples[min(len(samples)-1,int(.975*len(samples)))]]}

class ScaleSuite:
    """Physical matcher/team/graph benchmark for 10K, 100K and 1M populations."""
    def __init__(self,factory,batch_size=25_000,graph_sample_cap=50_000): self.factory=factory; self.batch_size=batch_size; self.graph_sample_cap=graph_sample_cap
    def _rss_mb(self):
        if resource is not None:
            value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return value/1024 if value>10_000 else value/(1024*1024)
        try:
            import psutil
            return psutil.Process().memory_info().rss/1048576
        except Exception: return 0.0
    def _graph_benchmark(self,n,seed):
        sample=min(n,self.graph_sample_cap); agents=self.factory.build(sample,seed=seed); graph=AdvancedKnowledgeGraph(); started=time.perf_counter()
        for agent in agents: graph.add_agent(agent)
        elapsed=time.perf_counter()-started; return {'graph_agents_sampled':sample,'graph_update_seconds':elapsed,'graph_updates_per_second':sample/max(elapsed,1e-12),'graph_stats':graph.stats()}
    def run(self,weave,sizes=(10_000,100_000,1_000_000),seed=7):
        req=weave.analyzer.analyze('research analyze summarize verify and plan'); rows=[]; native_obj=weave.matcher.native; modes=['python']+(['native'] if weave.matcher.native_available else [])
        for n in sizes:
            graph_metrics=self._graph_benchmark(n,seed); per_size=[]
            for mode in modes:
                weave.matcher.native=native_obj if mode=='native' else None; processed=0; top=[]; elapsed=0.; batches=0; selection_elapsed=0.; selections=0; rss_before=self._rss_mb()
                while processed<n:
                    count=min(self.batch_size,n-processed); agents=self.factory.build(count,seed=seed+batches); started=time.perf_counter(); ranked=weave.matcher.rank(req,agents); elapsed+=time.perf_counter()-started
                    top.extend(ranked[:20]); top=sorted(top,key=lambda r:r.score,reverse=True)[:100]
                    if ranked:
                        selection_started=time.perf_counter(); weave.selector.select(req,ranked[:100],max_agents=5); selection_elapsed+=time.perf_counter()-selection_started; selections+=1
                    processed+=count; batches+=1
                rss_after=self._rss_mb(); row={'agents':n,'mode':mode,'ranking_seconds':elapsed,'agents_per_second':n/max(elapsed,1e-12),'top_score':top[0].score if top else None,'batch_size':self.batch_size,'physical_agents_evaluated':processed,'team_selection_seconds':selection_elapsed,'team_selection_ops_per_second':selections/max(selection_elapsed,1e-12),'peak_rss_mb':max(rss_before,rss_after),**graph_metrics}
                if mode=='native' and native_obj and top: row['native_team_microbenchmark']=native_obj.benchmark_team_selection(req,top,iterations=200)
                per_size.append(row); rows.append(row)
            python_row=next((r for r in per_size if r['mode']=='python'),None); native_row=next((r for r in per_size if r['mode']=='native'),None)
            if python_row and native_row: native_row['native_speedup_vs_python']=python_row['ranking_seconds']/max(native_row['ranking_seconds'],1e-12)
        weave.matcher.native=native_obj; return rows
