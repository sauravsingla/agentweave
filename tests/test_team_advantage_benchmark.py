import asyncio

from scripts.team_advantage_benchmark import run_benchmark, validate_evidence


def test_team_advantage_benchmark_demonstrates_completion_quality_and_recovery():
    payload = asyncio.run(run_benchmark())
    validate_evidence(payload)

    summary = payload['summary']
    aw = summary['agentweave-team']
    assert aw['tasks'] == 12
    assert aw['completion_rate'] > summary['single-best-agent']['completion_rate']
    assert aw['completion_rate'] > summary['random-team']['completion_rate']
    assert aw['completion_rate'] > summary['capability-only-team']['completion_rate']
    assert aw['mean_quality'] > summary['single-best-agent']['mean_quality']
    assert aw['recovery_opportunities'] >= 1
    assert aw['recovery_success_rate'] is not None


def test_team_advantage_benchmark_is_seed_reproducible_for_selection_metrics():
    first = asyncio.run(run_benchmark(20260816))
    second = asyncio.run(run_benchmark(20260816))

    for strategy in first['summary']:
        assert first['summary'][strategy]['completion_rate'] == second['summary'][strategy]['completion_rate']
        assert first['summary'][strategy]['mean_quality'] == second['summary'][strategy]['mean_quality']
        assert first['summary'][strategy]['mean_cost'] == second['summary'][strategy]['mean_cost']
        assert first['summary'][strategy]['failure_events'] == second['summary'][strategy]['failure_events']
        assert first['summary'][strategy]['recovery_success_rate'] == second['summary'][strategy]['recovery_success_rate']
