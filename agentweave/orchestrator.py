from __future__ import annotations
import time
from .requirements import RequirementAnalyzer
from .graph import CapabilityGraph
from .advanced_graph import AdvancedKnowledgeGraph
from .persistence import ReputationStore
from .engine import AgentRegistry, TrustEngine, PlacementEngine, AgentMatcher
from .optimizer import GlobalTeamOptimizer
from .validation import SecurityValidator, BenchmarkValidator, ResultValidator, RetestPolicy, RetestManager, IdentityVerifier
from .semantic import SemanticResultVerifier
from .collaboration import CollaborationEngine, ConsensusEngine, ConflictResolver
from .a2a import InMemoryA2AAdapter
from .interoperability import A2AInteropSuite
from .identity import DIDResolver, VerifiableCredentialVerifier, RevocationRegistry, CertificateRotationManager, KeyManager, WorkloadAttestationVerifier
from .sandbox import DockerSandbox, SandboxPolicy
from .observability import Observability
from .policy import GovernancePolicyEngine, PolicyContext
from .lifecycle import LongRunningA2AClient
from .protocol_depth import PushNotificationConfigClient

class AgentWeave:
    def __init__(self,a2a=None,db_path='agentweave.db',*,store=None,security_validator=None,result_validator=None,semantic_verifier=None,policy_engine=None,use_native=True):
        self.store=store or ReputationStore(db_path)
        self.graph=CapabilityGraph(); self.knowledge_graph=AdvancedKnowledgeGraph(); self.registry=AgentRegistry(self.store,self.graph)
        self.analyzer=RequirementAnalyzer(); self.trust=TrustEngine(self.store); self.placement=PlacementEngine(); self.matcher=AgentMatcher(self.trust,self.placement,use_native=use_native); self.selector=GlobalTeamOptimizer()
        self.security=security_validator or SecurityValidator(); self.identity=IdentityVerifier(); self.result_validator=result_validator or ResultValidator(); self.semantic_verifier=semantic_verifier or SemanticResultVerifier(); self.retest_policy=RetestPolicy(); self.a2a=a2a or InMemoryA2AAdapter()
        self.collaboration=CollaborationEngine(self.a2a); self.consensus=ConsensusEngine(); self.conflicts=ConflictResolver(self.a2a)
        self.policy=policy_engine or GovernancePolicyEngine(); self.observability=Observability(self.store); self.interop=A2AInteropSuite(); self.lifecycle=LongRunningA2AClient(); self.push_notifications=PushNotificationConfigClient()
        self.did=DIDResolver(); self.vc=VerifiableCredentialVerifier(); self.revocations=RevocationRegistry(); self.cert_rotation=CertificateRotationManager(); self.keys=KeyManager(); self.attestation=WorkloadAttestationVerifier(); self.sandbox=DockerSandbox(); self.sandbox_policy=SandboxPolicy()

    def register(self,agent):
        with self.observability.tracer.span('agentweave.registry.register',agent_id=agent.agent_id):
            self.knowledge_graph.add_agent(agent)
            self.observability.audit.record('agent.registered',agent.agent_id,name=agent.name)
            self.observability.metrics.inc('agents_registered_total')
            return self.registry.register(agent)

    async def ingest_marketplace(self,marketplace,security_check=True,*,require_signed_cards=False,key_resolver=None,policy_context=None):
        with self.observability.tracer.span('agentweave.discovery.marketplace'):
            agents=await marketplace.list_agents()
        verdicts=[]
        for agent in agents:
            with self.observability.tracer.span('agentweave.onboarding.validate',agent_id=agent.agent_id):
                sec=self.security.validate(agent) if security_check else {'passed':True,'score':1.0,'problems':[],'warnings':[]}
                identity={'passed':True,'verified':False}
                card=agent.metadata.get('agent_card')
                if self.revocations.is_revoked(agent.agent_id): identity={'passed':False,'verified':False,'error':'agent-revoked'}
                elif require_signed_cards:
                    identity={'passed':False,'verified':False,'error':'signed-agent-card-required'}
                    if card and key_resolver:
                        try:
                            key=key_resolver(agent,card); claims=self.identity.verify_agent_card_jws(card,key) if key else None
                            if claims: identity={'passed':True,'verified':True,'claims':claims}; agent.trust.identity=1.0; agent.signature_verified=True
                        except Exception as exc: identity={'passed':False,'verified':False,'error':str(exc)}; agent.trust.identity=0.0
                req=self.analyzer.analyze('marketplace onboarding')
                policy=self.policy.evaluate(agent,req,policy_context or PolicyContext())
                registered=bool(sec.get('passed')) and bool(identity.get('passed')) and policy.allowed
                if registered: self.register(agent)
                verdict={'agent_id':agent.agent_id,'security':sec,'identity':identity,'policy':policy.__dict__,'registered':registered}
                verdicts.append(verdict); self.observability.audit.record('agent.onboarding',agent.agent_id,**verdict)
        return verdicts

    async def benchmark_agent(self,agent_id,cases,threshold=.7):
        agent=self.registry.get(agent_id)
        if not agent: raise KeyError(agent_id)
        validator=BenchmarkValidator(lambda a,p:self.a2a.invoke(a,p,context={'mode':'benchmark'}))
        with self.observability.tracer.span('agentweave.benchmark',agent_id=agent_id):
            verdict=await validator.run(agent,cases,threshold)
        self.register(agent); return verdict

    async def retest_due_agents(self,benchmark_factory,threshold=.7):
        validator=BenchmarkValidator(lambda a,p:self.a2a.invoke(a,p,context={'mode':'retest'})); manager=RetestManager(self.retest_policy,benchmark_factory)
        with self.observability.tracer.span('agentweave.retest'):
            results=await manager.run_due(self.registry.all(),validator,threshold)
        for agent_id in results:
            agent=self.registry.get(agent_id)
            if agent: self.register(agent)
        return results

    async def test_interoperability(self,targets,prompt='A2A interoperability test'):
        with self.observability.tracer.span('agentweave.a2a.interop',targets=len(targets)):
            results=await self.interop.run(targets,prompt)
        return [x.__dict__ for x in results]

    async def solve(self,text,*,domains=None,knowledge=None,local_only=False,max_latency_ms=None,privacy_level=None,max_agents=5,rounds=2,policy_context=None,semantic_verify=False):
        started_total=time.perf_counter()
        with self.observability.tracer.span('agentweave.requirement.analyze',requirement=text):
            req=self.analyzer.analyze(text,domains=domains,knowledge=knowledge,local_only=local_only,max_latency_ms=max_latency_ms,privacy_level=privacy_level)
        candidates=[]; policy_decisions={}
        with self.observability.tracer.span('agentweave.policy.filter',candidate_count=len(self.registry.all())):
            for agent in self.registry.all():
                decision=self.policy.evaluate(agent,req,policy_context or PolicyContext()); policy_decisions[agent.agent_id]=decision.__dict__
                if decision.allowed and not self.revocations.is_revoked(agent.agent_id): candidates.append(agent)
        with self.observability.tracer.span('agentweave.match.rank',requirement=text,candidates=len(candidates)):
            ranked=self.matcher.rank(req,candidates)
        with self.observability.tracer.span('agentweave.team.select',max_agents=max_agents):
            team=self.selector.select(req,ranked,max_agents=max_agents)
        explanation=self.observability.explainer.explain(req,ranked,team,policy_decisions)
        self.observability.audit.record('selection.explained',payload=explanation)
        if not team:
            return {'status':'no-suitable-agent','requirement':text,'required_capabilities':sorted(req.capabilities),'results':[],'native_acceleration':self.matcher.native_available,'policy':policy_decisions,'selection_explanation':explanation,'observability':self.observability.snapshot()}
        self.observability.audit.record('team.selected',payload={'agents':[m.agent.agent_id for m in team]})
        with self.observability.tracer.span('agentweave.a2a.collaboration',rounds=rounds,team_size=len(team)):
            collaboration_started=time.perf_counter(); transcript=await self.collaboration.deliberate(team,text,rounds=rounds); self.observability.metrics.observe('collaboration_latency_ms',(time.perf_counter()-collaboration_started)*1000)
        final_round=max((r['round'] for r in transcript),default=0); final_results=[r for r in transcript if r['round']==final_round]
        with self.observability.tracer.span('agentweave.consensus'):
            consensus=self.consensus.evaluate(final_results)
        with self.observability.tracer.span('agentweave.conflict_resolution'):
            resolution=await self.conflicts.resolve(team,text,final_results,consensus)
        with self.observability.tracer.span('agentweave.result_validation'):
            validation=self.result_validator.validate(final_results,req.capabilities,consensus=consensus)
            semantic=None
            if semantic_verify:
                semantic=await self.semantic_verifier.verify(final_results,text); validation['semantic']=semantic; validation['score']=.65*validation['score']+.35*semantic['score']; validation['passed']=validation['passed'] and semantic['score']>=.45
        per_agent={r['agent_id']:r for r in final_results}
        with self.observability.tracer.span('agentweave.reputation.update',agents=len(team)):
            for member in team:
                result=per_agent.get(member.agent.agent_id,{}); success=bool(result.get('success')) and validation['passed']; self.trust.update(member.agent,success,validation['score'],{'consensus':consensus,'resolution':resolution,'validation':validation}); self.register(member.agent)
        self.observability.metrics.observe('solve_latency_ms',(time.perf_counter()-started_total)*1000)
        self.observability.metrics.inc('solve_total',status='completed' if validation['passed'] else 'needs-review')
        return {'status':'completed' if validation['passed'] else 'needs-review','requirement':text,'required_capabilities':sorted(req.capabilities),'selected_agents':[m.agent.agent_id for m in team],'capability_coverage':self.graph.coverage(req,[m.agent for m in team]),'native_acceleration':self.matcher.native_available,'policy':policy_decisions,'selection_explanation':explanation,'transcript':transcript,'consensus':consensus,'resolution':resolution,'result_validation':validation,'semantic_validation':semantic,'observability':self.observability.snapshot()}
