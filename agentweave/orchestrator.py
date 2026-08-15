from __future__ import annotations
from .requirements import RequirementAnalyzer
from .graph import CapabilityGraph
from .persistence import ReputationStore
from .engine import AgentRegistry, TrustEngine, PlacementEngine, AgentMatcher, TeamSelector
from .validation import SecurityValidator, BenchmarkValidator, ResultValidator, RetestPolicy, RetestManager, IdentityVerifier
from .collaboration import CollaborationEngine, ConsensusEngine, ConflictResolver
from .a2a import InMemoryA2AAdapter

class AgentWeave:
    def __init__(self,a2a=None,db_path='agentweave.db',*,security_validator=None,result_validator=None,use_native=True):
        self.store=ReputationStore(db_path); self.graph=CapabilityGraph(); self.registry=AgentRegistry(self.store,self.graph)
        self.analyzer=RequirementAnalyzer(); self.trust=TrustEngine(self.store); self.placement=PlacementEngine(); self.matcher=AgentMatcher(self.trust,self.placement,use_native=use_native); self.selector=TeamSelector()
        self.security=security_validator or SecurityValidator(); self.identity=IdentityVerifier(); self.result_validator=result_validator or ResultValidator(); self.retest_policy=RetestPolicy(); self.a2a=a2a or InMemoryA2AAdapter()
        self.collaboration=CollaborationEngine(self.a2a); self.consensus=ConsensusEngine(); self.conflicts=ConflictResolver(self.a2a)

    async def ingest_marketplace(self,marketplace,security_check=True,*,require_signed_cards=False,key_resolver=None):
        agents=await marketplace.list_agents(); verdicts=[]
        for agent in agents:
            sec=self.security.validate(agent) if security_check else {'passed':True,'score':1.0,'problems':[],'warnings':[]}
            identity={'passed':True,'verified':False}
            card=agent.metadata.get('agent_card')
            if require_signed_cards:
                identity={'passed':False,'verified':False,'error':'signed-agent-card-required'}
                if card and key_resolver:
                    try:
                        key=key_resolver(agent,card)
                        if key:
                            claims=self.identity.verify_agent_card_jws(card,key)
                            identity={'passed':True,'verified':True,'claims':claims}; agent.trust.identity=1.0
                    except Exception as exc:
                        identity={'passed':False,'verified':False,'error':str(exc)}; agent.trust.identity=0.0
            registered=bool(sec.get('passed')) and bool(identity.get('passed'))
            if registered: self.registry.register(agent)
            verdicts.append({'agent_id':agent.agent_id,'security':sec,'identity':identity,'registered':registered})
        return verdicts

    async def benchmark_agent(self,agent_id,cases,threshold=.7):
        agent=self.registry.get(agent_id)
        if not agent: raise KeyError(agent_id)
        validator=BenchmarkValidator(lambda a,p:self.a2a.invoke(a,p,context={'mode':'benchmark'}))
        verdict=await validator.run(agent,cases,threshold); self.registry.register(agent); return verdict

    async def retest_due_agents(self,benchmark_factory,threshold=.7):
        validator=BenchmarkValidator(lambda a,p:self.a2a.invoke(a,p,context={'mode':'retest'}))
        manager=RetestManager(self.retest_policy,benchmark_factory)
        results=await manager.run_due(self.registry.all(),validator,threshold)
        for agent_id in results:
            agent=self.registry.get(agent_id)
            if agent: self.registry.register(agent)
        return results

    async def solve(self,text,*,domains=None,knowledge=None,local_only=False,max_latency_ms=None,privacy_level=None,max_agents=5,rounds=2):
        req=self.analyzer.analyze(text,domains=domains,knowledge=knowledge,local_only=local_only,max_latency_ms=max_latency_ms,privacy_level=privacy_level)
        ranked=self.matcher.rank(req,self.registry.all()); team=self.selector.select(req,ranked,max_agents=max_agents)
        if not team: return {'status':'no-suitable-agent','requirement':text,'required_capabilities':sorted(req.capabilities),'results':[],'native_acceleration':self.matcher.native_available}
        transcript=await self.collaboration.deliberate(team,text,rounds=rounds)
        final_round=max((r['round'] for r in transcript),default=0); final_results=[r for r in transcript if r['round']==final_round]
        consensus=self.consensus.evaluate(final_results); resolution=await self.conflicts.resolve(team,text,final_results,consensus)
        validation=self.result_validator.validate(final_results,req.capabilities,consensus=consensus)
        per_agent={r['agent_id']:r for r in final_results}
        for member in team:
            r=per_agent.get(member.agent.agent_id,{}); success=bool(r.get('success')) and validation['passed']; self.trust.update(member.agent,success,validation['score'],{'consensus':consensus,'resolution':resolution,'validation':validation})
            self.registry.register(member.agent)
        return {'status':'completed' if validation['passed'] else 'needs-review','requirement':text,'required_capabilities':sorted(req.capabilities),'selected_agents':[m.agent.agent_id for m in team],'capability_coverage':self.graph.coverage(req,[m.agent for m in team]),'native_acceleration':self.matcher.native_available,'transcript':transcript,'consensus':consensus,'resolution':resolution,'result_validation':validation}
