import pytest
from agentweave import AgentWeave, AgentProfile, Capability, TrustVector, ExecutionProfile, InMemoryA2AAdapter, StaticMarketplace, BenchmarkCase
from agentweave.graph import CapabilityGraph
from agentweave.validation import ResultValidator, RetestPolicy

@pytest.mark.asyncio
async def test_full_flow(tmp_path):
    bus=InMemoryA2AAdapter(); weave=AgentWeave(bus,tmp_path/'aw.db')
    a=AgentProfile('a','Researcher',[Capability('research',.95,True)],domains=['science'],knowledge=['evidence'],trust=TrustVector(identity=1,capability=.9,domain=.9,execution=.9,security=.9,collaboration=.8,historical=.8))
    b=AgentProfile('b','Summarizer',[Capability('summarization',.9,True)],trust=TrustVector(identity=1,capability=.9,domain=.8,execution=.9,security=.9,collaboration=.9,historical=.8))
    await weave.ingest_marketplace(StaticMarketplace([a,b]))
    bus.register_handler('a',lambda p:{'result':'evidence','decision':'accept'})
    bus.register_handler('b',lambda p:{'result':'summary','decision':'accept'})
    out=await weave.solve('Research the evidence and summarize it',rounds=2)
    assert out['status']=='completed'
    assert set(out['selected_agents'])=={'a','b'}
    assert out['result_validation']['passed']
    assert out['consensus']['consensus']
    assert a.tasks_completed==1 and b.tasks_completed==1

@pytest.mark.asyncio
async def test_benchmark_updates_capability(tmp_path):
    bus=InMemoryA2AAdapter(); weave=AgentWeave(bus,tmp_path/'aw.db')
    a=AgentProfile('a','Coder',[Capability('coding',.2,False)])
    weave.registry.register(a); bus.register_handler('a',lambda p:{'result':'correct'})
    cases=[BenchmarkCase('coding','write code',lambda r:1.0)]
    result=await weave.benchmark_agent('a',cases)
    assert result['passed'] and a.capabilities[0].validated and a.capabilities[0].proficiency==1.0

@pytest.mark.asyncio
async def test_edge_local_only(tmp_path):
    bus=InMemoryA2AAdapter(); weave=AgentWeave(bus,tmp_path/'aw.db')
    cloud=AgentProfile('c','Cloud',[Capability('summarization',1,True)],execution=ExecutionProfile(location='cloud'))
    edge=AgentProfile('e','Edge',[Capability('summarization',.8,True)],execution=ExecutionProfile(location='edge',privacy_level='local-only'))
    await weave.ingest_marketplace(StaticMarketplace([cloud,edge])); bus.register_handler('e',lambda p:{'result':'local'})
    out=await weave.solve('Summarize locally only',local_only=True,rounds=1)
    assert out['selected_agents']==['e']

def test_graph_and_persistence(tmp_path):
    weave=AgentWeave(db_path=tmp_path/'aw.db')
    a=AgentProfile('a','A',[Capability('analysis',.9,True)],knowledge=['graphs'])
    weave.registry.register(a)
    assert weave.graph.candidate_agents(weave.analyzer.analyze('analyze this'))==['a']
    clone=AgentWeave(db_path=tmp_path/'aw.db'); clone.registry.load_persisted(); assert clone.registry.get('a').name=='A'

def test_retest_policy():
    a=AgentProfile('a','A',[Capability('analysis')])
    assert RetestPolicy().due(a)
