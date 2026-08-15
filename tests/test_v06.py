import asyncio, hashlib, hmac
import pytest
from agentweave import (
    AdvancedKnowledgeGraph, PushNotificationReceiver, VerificationBenchmark,
    RedTeamValidationSuite, ChaosReliabilitySuite, AgentWeaveSDK, AgentWeave,
)

def test_push_receiver_hmac_verification():
    receiver=PushNotificationReceiver('secret')
    body=b'{"task":"1"}'
    sig=hmac.new(b'secret',body,hashlib.sha256).hexdigest()
    assert receiver.verify(body,'sha256='+sig)
    assert not receiver.verify(body,'sha256='+'00'*32)

def test_knowledge_graph_contradictions_and_retrieval():
    graph=AdvancedKnowledgeGraph()
    graph.add_concept('machine learning','knowledge',aliases=['ml'],parents=['artificial intelligence'])
    graph.add_contradiction('safe','unsafe')
    assert 'unsafe' in graph.contradictions('safe')
    rows=graph.retrieve('machine learning',limit=3)
    assert rows and rows[0]['name']=='machine learning'

def test_verification_calibration_metrics():
    bench=VerificationBenchmark(); rows=[(.9,1),(.8,1),(.2,0),(.1,0)]
    assert bench.brier_score(rows)<.1
    assert bench.classification_metrics(rows)['accuracy']==1.0
    assert bench.expected_calibration_error(rows)>=0

def test_red_team_core_cases_pass():
    rows=RedTeamValidationSuite().run()
    assert rows
    assert all(x.passed for x in rows)
    names={x.name for x in rows}
    assert {'ssrf-link-local-block','tool-abuse-policy-block','spoofed-identity-rejected','sybil-collusion-detection'} <= names

@pytest.mark.asyncio
async def test_chaos_reliability_suite():
    rows=await ChaosReliabilitySuite().run()
    assert all(x.passed for x in rows)

def test_sdk_api_version():
    sdk=AgentWeaveSDK(AgentWeave(db_path=':memory:',use_native=False))
    assert sdk.API_VERSION=='1'
    assert isinstance(sdk.graph_stats(),dict)
