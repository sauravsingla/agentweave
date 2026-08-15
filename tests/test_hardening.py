import json
import pytest
from agentweave import AgentWeave, AgentProfile, Capability, ExecutionProfile, InMemoryA2AAdapter
from agentweave.validation import SecurityValidator, ResultValidator, BenchmarkCase


def test_security_validator_rejects_unsafe_endpoint():
    a=AgentProfile('x','X',[Capability('analysis')],execution=ExecutionProfile(endpoint='http://example.com'))
    out=SecurityValidator().validate(a)
    assert not out['passed']
    assert 'endpoint-not-tls' in out['problems']


def test_result_validator_composite_quality():
    v=ResultValidator(min_score=.5)
    results=[
        {'success':True,'matched_capabilities':['analysis'],'response':{'result':'yes','evidence':['source-a']}},
        {'success':True,'matched_capabilities':['analysis'],'response':{'result':'yes','evidence':['source-b']}},
    ]
    out=v.validate(results,{'analysis'},consensus={'agreement':1.0})
    assert out['passed']
    assert out['coverage']==1.0
    assert out['consistency']==1.0
    assert out['evidence']==1.0


@pytest.mark.asyncio
async def test_dynamic_retest_executes(tmp_path):
    bus=InMemoryA2AAdapter(); weave=AgentWeave(bus,tmp_path/'aw.db')
    a=AgentProfile('a','A',[Capability('analysis',.2,False)])
    weave.registry.register(a)
    bus.register_handler('a',lambda p:{'result':'ok'})
    def factory(agent):
        return [BenchmarkCase('analysis','benchmark',lambda r:1.0)]
    out=await weave.retest_due_agents(factory)
    assert out['a']['passed']
    assert a.capabilities[0].validated
    assert a.last_tested_at


@pytest.mark.asyncio
async def test_signed_card_requirement_blocks_unsigned(tmp_path):
    class Marketplace:
        async def list_agents(self):
            return [AgentProfile('a','A',[Capability('analysis')],metadata={'agent_card':{'name':'A'}})]
    weave=AgentWeave(db_path=tmp_path/'aw.db')
    out=await weave.ingest_marketplace(Marketplace(),require_signed_cards=True,key_resolver=lambda a,c:None)
    assert not out[0]['registered']
    assert weave.registry.get('a') is None
