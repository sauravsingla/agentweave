import pytest

from agentweave import (
    AgentProfile,
    AgentWeave,
    Capability,
    ExecutionProfile,
    InMemoryA2AAdapter,
    TrustVector,
)


def _trust(value):
    return TrustVector(
        identity=value,
        capability=value,
        domain=value,
        execution=value,
        security=value,
        collaboration=value,
        historical=value,
    )


def _agent(agent_id, trust, latency_ms=10):
    return AgentProfile(
        agent_id,
        agent_id.title(),
        [Capability('analysis', proficiency=1.0, validated=True)],
        trust=_trust(trust),
        execution=ExecutionProfile(latency_ms=latency_ms),
    )


@pytest.mark.asyncio
async def test_runtime_failure_degrades_trust_selects_replacement_and_completes():
    bus = InMemoryA2AAdapter()
    primary = _agent('primary', .95, 5)
    backup = _agent('backup', .70, 20)

    def fail(_):
        raise RuntimeError('simulated-primary-failure')

    bus.register_handler('primary', fail)
    bus.register_handler('backup', lambda _: {'result': 'recovered result', 'decision': 'accept', 'evidence': ['recovery-proof']})

    weave = AgentWeave(a2a=bus, db_path=':memory:', use_native=False)
    weave.register(primary)
    weave.register(backup)
    historical_before = primary.trust.historical

    result = await weave.solve('analyze this workload', max_agents=1, rounds=1, max_failovers=2)

    assert result['selected_agents'] == ['primary']
    assert result['effective_agents'] == ['backup']
    assert result['recovery']['attempted'] is True
    assert result['recovery']['failed_agent_ids'] == ['primary']
    assert result['recovery']['recovered_agent_ids'] == ['backup']
    assert result['recovery']['events'][0] == {
        'failed_agent_id': 'primary',
        'replacement_agent_id': 'backup',
        'attempt': 1,
        'success': True,
        'error': None,
    }
    assert result['status'] == 'completed'
    assert result['result_validation']['passed'] is True
    assert primary.trust.historical < historical_before
    assert primary.tasks_completed == 1
    assert primary.tasks_succeeded == 0
    assert backup.tasks_completed == 1
    assert backup.tasks_succeeded == 1
    assert any(r['agent_id'] == 'primary' and not r['success'] for r in result['transcript'])
    assert any(r['agent_id'] == 'backup' and r['success'] and r.get('recovery') for r in result['transcript'])


@pytest.mark.asyncio
async def test_runtime_recovery_retries_next_candidate_after_replacement_failure():
    bus = InMemoryA2AAdapter()
    primary = _agent('primary', .98, 5)
    first_backup = _agent('backup-one', .80, 10)
    second_backup = _agent('backup-two', .65, 20)

    def fail_primary(_):
        raise RuntimeError('primary-down')

    def fail_first_backup(_):
        raise RuntimeError('backup-one-down')

    bus.register_handler('primary', fail_primary)
    bus.register_handler('backup-one', fail_first_backup)
    bus.register_handler('backup-two', lambda _: {'result': 'final success', 'decision': 'accept', 'evidence': ['proof']})

    weave = AgentWeave(a2a=bus, db_path=':memory:', use_native=False)
    for agent in (primary, first_backup, second_backup):
        weave.register(agent)

    first_backup_before = first_backup.trust.historical
    result = await weave.solve('analyze this workload', max_agents=1, rounds=1, max_failovers=2)

    assert result['status'] == 'completed'
    assert result['effective_agents'] == ['backup-two']
    assert result['recovery']['recovered_agent_ids'] == ['backup-two']
    assert [event['replacement_agent_id'] for event in result['recovery']['events']] == ['backup-one', 'backup-two']
    assert [event['success'] for event in result['recovery']['events']] == [False, True]
    assert first_backup.trust.historical < first_backup_before
    assert first_backup.tasks_completed == 1
    assert second_backup.tasks_succeeded == 1
    recovery_rows = [r for r in result['transcript'] if r.get('recovery')]
    assert [r['agent_id'] for r in recovery_rows] == ['backup-one', 'backup-two']
    assert [r['success'] for r in recovery_rows] == [False, True]
