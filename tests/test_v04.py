import json, pytest
from agentweave import (
    AgentWeave, AgentProfile, Capability, TrustVector, ExecutionProfile,
    SemanticResultVerifier, GlobalTeamOptimizer, GovernancePolicyEngine, PolicyContext,
    SandboxPolicy, AdversarialAgent, AdversarialTestSuite, AdvancedKnowledgeGraph,
    AgentWeaveConfig, InteropTarget
)

@pytest.mark.asyncio
async def test_semantic_verification():
    v=SemanticResultVerifier()
    out=await v.verify([
        {'success':True,'response':{'result':'Evidence supports the result. Source: [1]'}},
        {'success':True,'response':{'result':'Evidence supports the result. Source: [2]'}}
    ],'question')
    assert out['score']>0 and out['consistency']>0


def test_policy_governance():
    p=GovernancePolicyEngine(allowed_jurisdictions={'IN'},blocked_tools={'shell'})
    a=AgentProfile('a','A',[Capability('analysis')],metadata={'tools':['shell']})
    req=AgentWeave(db_path=':memory:').analyzer.analyze('analyze')
    d=p.evaluate(a,req,PolicyContext(jurisdiction='IN'))
    assert not d.allowed and any('blocked-tools' in x for x in d.reasons)


def test_sandbox_policy_requires_digest():
    p=SandboxPolicy(); assert not p.validate_image('python:3.11')['passed']; assert p.validate_image('repo/image@sha256:'+'a'*64)['passed']


def test_advanced_graph_inheritance():
    g=AdvancedKnowledgeGraph(); g.inherit('graph-neural-network','machine-learning')
    a=AgentProfile('a','A',[Capability('graph-neural-network',.9,True)])
    g.add_agent(a); assert g.agent_score('a',['graph-neural-network'])>.5


def test_adversarial_sybil_detection():
    agents=AdversarialAgent.sybil_cluster('op',3); groups=AdversarialTestSuite().detect_sybil(agents); assert len(groups['op'])==3


def test_config_json(tmp_path):
    p=tmp_path/'config.json'; p.write_text(json.dumps({'db_path':'x.db','max_agents':7,'custom':1})); c=AgentWeaveConfig.load(p); assert c.max_agents==7 and c.settings['custom']==1

@pytest.mark.asyncio
async def test_orchestrator_policy_and_semantic(tmp_path):
    from agentweave import InMemoryA2AAdapter, StaticMarketplace
    bus=InMemoryA2AAdapter(); w=AgentWeave(bus,tmp_path/'db.sqlite')
    a=AgentProfile('a','Analyst',[Capability('analysis',.95,True)],trust=TrustVector(identity=.9,capability=.9,domain=.9,execution=.9,security=.9,collaboration=.9,historical=.9))
    await w.ingest_marketplace(StaticMarketplace([a])); bus.register_handler('a',lambda p:{'result':'analysis result','decision':'accept'})
    out=await w.solve('analyze this',rounds=1,semantic_verify=True)
    assert out['selected_agents']==['a']; assert out['semantic_validation'] is not None


def test_interop_target_model():
    x=InteropTarget('python','https://example.test/.well-known/agent-card.json','a2a-python'); assert x.implementation=='a2a-python'
