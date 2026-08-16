import pytest

from agentweave import (
    A2AAdapter,
    AgentProfile,
    Capability,
    DurableAgentWeave,
    ExecutionProfile,
    TrustVector,
    WorkflowStep,
)


class RecordingAdapter(A2AAdapter):
    def __init__(self):
        self.handlers = {}
        self.calls = []

    def register_handler(self, agent_id, handler):
        self.handlers[agent_id] = handler

    async def invoke(self, agent, task, context=None):
        context = dict(context or {})
        self.calls.append({'agent_id': agent.agent_id, 'task': task, 'context': context})
        handler = self.handlers[agent.agent_id]
        result = handler(task, context)
        if hasattr(result, '__await__'):
            result = await result
        return result if isinstance(result, dict) else {'result': result}


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


def _agent(agent_id, trust=.8, latency_ms=10):
    return AgentProfile(
        agent_id,
        agent_id.title(),
        [Capability('analysis', proficiency=1.0, validated=True)],
        trust=_trust(trust),
        execution=ExecutionProfile(latency_ms=latency_ms),
    )


def _steps():
    return [
        WorkflowStep('step-1', 'step one', {'analysis'}),
        WorkflowStep('step-2', 'step two', {'analysis'}),
        WorkflowStep('step-3', 'step three', {'analysis'}),
        WorkflowStep('step-4', 'step four', {'analysis'}),
    ]


@pytest.mark.asyncio
async def test_completed_steps_are_not_replayed_after_process_restart(tmp_path):
    db = tmp_path / 'durable.db'
    workflow_id = 'restart-proof'

    first_bus = RecordingAdapter()
    primary = _agent('primary', .95)

    def primary_handler(task, _context):
        if task == 'step three':
            raise RuntimeError('simulated-process-boundary-failure')
        return {'result': f'primary:{task}'}

    first_bus.register_handler('primary', primary_handler)
    first = DurableAgentWeave(a2a=first_bus, db_path=db, use_native=False)
    first.register(primary)

    interrupted = await first.run_workflow(_steps(), workflow_id=workflow_id, max_failovers=0)

    assert interrupted['status'] == 'failed'
    assert interrupted['next_step_index'] == 2
    assert [x['step_id'] for x in interrupted['completed_steps']] == ['step-1', 'step-2']
    assert [x['task'] for x in first_bus.calls] == ['step one', 'step two', 'step three']

    # Simulate a fresh process: construct a new AgentWeave instance against the
    # same durable DB. Only the replacement is available in the restarted process.
    second_bus = RecordingAdapter()
    replacement = _agent('replacement', .80)
    second_bus.register_handler('replacement', lambda task, _context: {'result': f'replacement:{task}'})
    second = DurableAgentWeave(a2a=second_bus, db_path=db, use_native=False)
    second.register(replacement)

    resumed = await second.resume_workflow(workflow_id, max_failovers=1)

    assert resumed['status'] == 'completed'
    assert resumed['next_step_index'] == 4
    assert [x['step_id'] for x in resumed['completed_steps']] == ['step-1', 'step-2', 'step-3', 'step-4']
    assert [x['task'] for x in second_bus.calls] == ['step three', 'step four']
    assert all(x['task'] not in {'step one', 'step two'} for x in second_bus.calls)
    assert resumed['completed_steps'][2]['agent_id'] == 'replacement'

    persisted = second.workflow_state(workflow_id)
    assert persisted['status'] == 'completed'
    assert persisted['next_step_index'] == 4


@pytest.mark.asyncio
async def test_failed_step_is_replaced_without_replaying_prior_step(tmp_path):
    bus = RecordingAdapter()
    primary = _agent('primary', .98, 5)
    backup = _agent('backup', .70, 20)

    bus.register_handler('primary', lambda _task, _context: (_ for _ in ()).throw(RuntimeError('primary-down')))
    bus.register_handler('backup', lambda task, _context: {'result': f'backup:{task}'})

    weave = DurableAgentWeave(a2a=bus, db_path=tmp_path / 'failover.db', use_native=False)
    weave.register(primary)
    weave.register(backup)

    result = await weave.run_workflow(
        [WorkflowStep('critical-step', 'critical work', {'analysis'})],
        workflow_id='failover-proof',
        max_failovers=1,
    )

    assert result['status'] == 'completed'
    assert len(result['failed_attempts']) == 1
    assert result['failed_attempts'][0]['agent_id'] == 'primary'
    assert result['completed_steps'][0]['agent_id'] == 'backup'
    assert result['completed_steps'][0]['recovered'] is True
    assert [x['agent_id'] for x in bus.calls] == ['primary', 'backup']
    assert bus.calls[0]['context']['idempotency_key'] == bus.calls[1]['context']['idempotency_key']
    assert primary.tasks_completed == 1
    assert primary.tasks_succeeded == 0
    assert backup.tasks_completed == 1
    assert backup.tasks_succeeded == 1


@pytest.mark.asyncio
async def test_resume_of_completed_workflow_is_idempotent(tmp_path):
    bus = RecordingAdapter()
    agent = _agent('worker', .9)
    bus.register_handler('worker', lambda task, _context: {'result': task})
    weave = DurableAgentWeave(a2a=bus, db_path=tmp_path / 'complete.db', use_native=False)
    weave.register(agent)

    finished = await weave.run_workflow(
        [WorkflowStep('only', 'run once', {'analysis'})],
        workflow_id='completed-proof',
    )
    assert finished['status'] == 'completed'
    assert len(bus.calls) == 1

    resumed = await weave.resume_workflow('completed-proof')
    assert resumed['status'] == 'completed'
    assert len(bus.calls) == 1
