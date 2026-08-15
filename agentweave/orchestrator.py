from __future__ import annotations
from .requirements import RequirementAnalyzer
from .graph import CapabilityGraph
from .persistence import ReputationStore
from .engine import AgentRegistry, TrustEngine, PlacementEngine, AgentMatcher, TeamSelector
from .validation import SecurityValidator, BenchmarkValidator, ResultValidator, RetestPolicy
from .collaboration import CollaborationEngine, ConsensusEngine, ConflictResolver
from .a2a import InMemoryA2AAdapter

class AgentWeave:
    def __init__(self,a2a=None,db_path='agentweave.db'):
        self.store=ReputationStore(db_path); self.graph=CapabilityGraph(); self.registry=AgentRegistry(self.store,self.graph)
        self.analyzer=RequirementAnalyzer(); self.trust=TrustEngine(self.store); self.placement=PlacementEngine(); self.matcher=AgentMatcher(self.trust,self.placement); self.selector=TeamSelector()
        self.security=SecurityValidator(); self.result_validator=ResultValidator(); self.retest_policy=RetestPolicy(); self.a2a=a2a or InMemoryA2AAdapter()
        self.collaboration=CollaborationEngine(self.a2a); self.consensus=ConsensusEngine(); self.conflicts=ConflictResolver(self.a2a)

    async def ingest_marketplace(self,marketplace,security_check=True):
        agents=await marketplace.list_agents(); verdicts=[]
        for agent in agents:
            sec=self.security.validate(agent) if security_check else {'passed':True,'score':1.0}
            if sec['passed']: self.registry.register(agent)
            verdicts.append({'agent_id':agent.agent_id,'security':sec,'registered':sec['passed']})
        return verdicts

    async def benchmark_agent(self,agent_id,cases,threshold=.7):
        agent=self.registry.get(agent_id)
        if not agent: raise KeyError(agent_id)
        validator=BenchmarkValidator(lambda a,p:self.a2a.invoke(a,p,context={'mode':'benchmark'}))
        verdict=await validator.run(agent,cases,threshold); self.registry.register(agent); return verdict

    async def solve(self,text,*,domains=None,knowledge=None,local_only=False,max_latency_ms=None,privacy_level=None,max_agents=5,rounds=2):
        req=self.analyzer.analyze(text,domains=domains,knowledge=knowledge,local_only=local_only,max_latency_ms=max_latency_ms,privacy_level=privacy_level)
        ranked=self.matcher.rank(req,self.registry.all()); team=self.selector.select(req,ranked,max_agents=max_agents)
        if not team: return {'status':'no-suitable-agent','requirement':text,'required_capabilities':sorted(req.capabilities),'results':[]}
        transcript=await self.collaboration.deliberate(team,text,rounds=rounds)
        final_round=max((r['round'] for r in transcript),default=0); final_results=[r for r in transcript if r['round']==final_round]
        consensus=self.consensus.evaluate(final_results); resolution=await self.conflicts.resolve(team,text,final_results,consensus)
        validation=self.result_validator.validate(final_results,req.capabilities)
        per_agent={r['agent_id']:r for r in final_results}
        for member in team:
            r=per_agent.get(member.agent.agent_id,{}); success=bool(r.get('success')) and validation['passed']; self.trust.update(member.agent,success,validation['score'],{'consensus':consensus,'validation':validation})
            self.registry.register(member.agent)
        return {'status':'completed' if validation['passed'] else 'needs-review','requirement':text,'required_capabilities':sorted(req.capabilities),'selected_agents':[m.agent.agent_id for m in team],'capability_coverage':self.graph.coverage(req,[m.agent for m in team]),'transcript':transcript,'consensus':consensus,'resolution':resolution,'result_validation':validation}
