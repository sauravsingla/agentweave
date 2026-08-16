from agentweave import AgentProfile, Capability, ExecutionProfile, Requirement, TrustVector
from agentweave.engine import AgentMatcher, PlacementEngine, TrustEngine
from agentweave.optimizer import GlobalTeamOptimizer


def _trust(value):
    return TrustVector(*(value for _ in range(7)))


def test_global_team_optimizer_excludes_non_contributing_agents():
    req = Requirement('analyze and verify', {'analysis', 'verification'})
    relevant = AgentProfile(
        'relevant',
        'Relevant',
        [Capability('analysis', 0.9, True), Capability('verification', 0.9, True)],
        trust=_trust(0.8),
        execution=ExecutionProfile(location='cloud', latency_ms=30, cost=0.1),
    )
    irrelevant = AgentProfile(
        'irrelevant',
        'Irrelevant',
        [Capability('translation', 1.0, True)],
        trust=_trust(1.0),
        execution=ExecutionProfile(location='edge', latency_ms=1, cost=0.0),
    )

    matcher = AgentMatcher(TrustEngine(), PlacementEngine(), use_native=False)
    ranked = matcher.rank(req, [relevant, irrelevant])
    team = GlobalTeamOptimizer().select(req, ranked, max_agents=2)

    assert [item.agent.agent_id for item in team] == ['relevant']
