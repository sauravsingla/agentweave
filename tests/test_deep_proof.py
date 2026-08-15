from agentweave import AgentWeave, SyntheticAgentFactory
from agentweave.research import ResearchBenchmark, ScaleSuite
from agentweave.lifecycle import LongRunningA2AClient
from agentweave.security_lab import AdversarialValidationSuite


def test_research_baselines_and_ablations():
    w=AgentWeave(db_path=':memory:',use_native=False)
    for a in SyntheticAgentFactory().build(60,seed=5): w.register(a)
    suite=ResearchBenchmark(seed=9)
    rows=suite.evaluate(w,['research and summarize','analyze and verify'],max_agents=3)
    methods={x.method for x in rows}
    assert {'agentweave','single-best','random','trust-only','capability-greedy','ablation-no-trust','ablation-no-placement'} <= methods
    aggregate=suite.aggregate(rows)
    assert 0 <= aggregate['agentweave']['coverage'] <= 1
    ci=suite.bootstrap_delta(rows,iterations=100)
    assert len(ci['ci95'])==2


def test_scale_suite_is_physical_and_batched():
    w=AgentWeave(db_path=':memory:',use_native=False)
    rows=ScaleSuite(SyntheticAgentFactory(),batch_size=100).run(w,(250,))
    assert rows[0]['agents']==250
    assert rows[0]['physical_agents_evaluated']==250
    assert rows[0]['batch_size']==100


def test_lifecycle_status_normalization():
    assert LongRunningA2AClient._status({'status':{'state':'TASK_STATE_COMPLETED'}})=='completed'
    assert LongRunningA2AClient._status({'task':{'status':{'state':'TASK_STATE_CANCELED'}}})=='canceled'


def test_adversarial_suite_detects_core_cases():
    rows=AdversarialValidationSuite().run()
    by_name={r.name:r for r in rows}
    assert by_name['agent-card-prompt-injection'].passed
    assert by_name['sybil-cluster-detection'].passed
