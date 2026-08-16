from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from .models import Requirement


@dataclass
class WorkflowStep:
    """One durable workflow step.

    ``step_id`` is stable across retries and process restarts. AgentWeave passes a
    deterministic idempotency key derived from ``workflow_id`` and ``step_id`` to
    the selected agent so remote implementations can deduplicate an in-flight retry.
    """

    step_id: str
    task: str
    capabilities: set[str] = field(default_factory=set)
    domains: set[str] = field(default_factory=set)
    knowledge: set[str] = field(default_factory=set)
    local_only: bool = False
    max_latency_ms: float | None = None
    privacy_level: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        data = asdict(self)
        for key in ('capabilities', 'domains', 'knowledge'):
            data[key] = sorted(data[key])
        return data

    @classmethod
    def from_dict(cls, data):
        item = dict(data)
        for key in ('capabilities', 'domains', 'knowledge'):
            item[key] = set(item.get(key) or [])
        return cls(**item)


@dataclass
class WorkflowCheckpoint:
    workflow_id: str
    status: str
    steps: list[dict[str, Any]]
    next_step_index: int = 0
    completed_steps: list[dict[str, Any]] = field(default_factory=list)
    failed_attempts: list[dict[str, Any]] = field(default_factory=list)
    current_agent_id: str | None = None
    version: int = 0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**dict(data))


class DurableWorkflowEngine:
    """Checkpointed multi-step orchestration with agent replacement and resume.

    Completed steps are persisted before the next step begins. If the process dies,
    a new AgentWeave instance can load the checkpoint and continue at
    ``next_step_index`` without replaying already-completed steps. The currently
    in-flight step uses at-least-once semantics; a deterministic idempotency key is
    supplied to agents to allow exactly-once effects when the remote side supports
    deduplication.
    """

    def __init__(self, a2a, matcher, trust, registry, store, register_callback=None, observability=None):
        required = ('save_workflow_checkpoint', 'load_workflow_checkpoint')
        missing = [name for name in required if not hasattr(store, name)]
        if missing:
            raise TypeError(f'checkpoint-capable store required; missing: {", ".join(missing)}')
        self.a2a = a2a
        self.matcher = matcher
        self.trust = trust
        self.registry = registry
        self.store = store
        self.register_callback = register_callback
        self.observability = observability

    @staticmethod
    def _normalise_steps(steps):
        result = []
        seen = set()
        for raw in steps:
            step = raw if isinstance(raw, WorkflowStep) else WorkflowStep.from_dict(raw)
            if not step.step_id:
                raise ValueError('workflow step_id is required')
            if step.step_id in seen:
                raise ValueError(f'duplicate workflow step_id: {step.step_id}')
            if not step.task:
                raise ValueError(f'workflow step {step.step_id} task is required')
            seen.add(step.step_id)
            result.append(step)
        if not result:
            raise ValueError('workflow requires at least one step')
        return result

    def _save(self, checkpoint):
        checkpoint.version += 1
        self.store.save_workflow_checkpoint(checkpoint.workflow_id, checkpoint.to_dict())
        if self.observability:
            self.observability.audit.record(
                'workflow.checkpoint.saved',
                checkpoint.workflow_id,
                status=checkpoint.status,
                next_step_index=checkpoint.next_step_index,
                version=checkpoint.version,
            )
            self.observability.metrics.inc('workflow_checkpoints_total', status=checkpoint.status)

    def state(self, workflow_id):
        payload = self.store.load_workflow_checkpoint(workflow_id)
        return WorkflowCheckpoint.from_dict(payload) if payload else None

    def list_states(self, limit=100):
        if not hasattr(self.store, 'list_workflow_checkpoints'):
            raise TypeError('store does not support listing workflow checkpoints')
        return [WorkflowCheckpoint.from_dict(x) for x in self.store.list_workflow_checkpoints(limit=limit)]

    def _requirement(self, step):
        return Requirement(
            text=step.task,
            capabilities={str(x).lower() for x in step.capabilities},
            domains={str(x).lower() for x in step.domains},
            knowledge={str(x).lower() for x in step.knowledge},
            local_only=step.local_only,
            max_latency_ms=step.max_latency_ms,
            privacy_level=step.privacy_level,
        )

    def _record_outcome(self, agent, success, detail):
        self.trust.update(agent, success, 1.0 if success else 0.0, detail)
        if self.register_callback:
            self.register_callback(agent)

    async def start(self, steps, *, workflow_id=None, max_failovers=2):
        steps = self._normalise_steps(steps)
        workflow_id = workflow_id or str(uuid.uuid4())
        existing = self.state(workflow_id)
        if existing is not None:
            expected = [s.to_dict() for s in steps]
            if existing.steps != expected:
                raise ValueError(f'workflow {workflow_id} already exists with a different definition')
            return await self._execute(existing, max_failovers=max_failovers)

        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow_id,
            status='running',
            steps=[s.to_dict() for s in steps],
        )
        self._save(checkpoint)
        return await self._execute(checkpoint, max_failovers=max_failovers)

    async def resume(self, workflow_id, *, max_failovers=2):
        checkpoint = self.state(workflow_id)
        if checkpoint is None:
            raise KeyError(f'workflow checkpoint not found: {workflow_id}')
        if checkpoint.status == 'completed':
            return self._result(checkpoint)
        checkpoint.status = 'running'
        checkpoint.current_agent_id = None
        self._save(checkpoint)
        return await self._execute(checkpoint, max_failovers=max_failovers)

    def _result(self, checkpoint):
        return {
            'workflow_id': checkpoint.workflow_id,
            'status': checkpoint.status,
            'next_step_index': checkpoint.next_step_index,
            'total_steps': len(checkpoint.steps),
            'completed_steps': list(checkpoint.completed_steps),
            'failed_attempts': list(checkpoint.failed_attempts),
            'checkpoint_version': checkpoint.version,
        }

    async def _execute(self, checkpoint, *, max_failovers=2):
        max_failovers = max(0, int(max_failovers))
        steps = [WorkflowStep.from_dict(x) for x in checkpoint.steps]

        while checkpoint.next_step_index < len(steps):
            step_index = checkpoint.next_step_index
            step = steps[step_index]
            req = self._requirement(step)
            attempted_ids = set()
            last_error = None

            # One primary attempt plus up to ``max_failovers`` replacement attempts.
            for attempt in range(1, max_failovers + 2):
                candidates = [
                    a for a in self.registry.all()
                    if a.agent_id not in attempted_ids and a.execution.available
                ]
                ranked = self.matcher.rank(req, candidates)
                selected = next(
                    (
                        row for row in ranked
                        if row.score > 0 and (not req.capabilities or not row.missing_capabilities)
                    ),
                    None,
                )
                if selected is None:
                    last_error = 'no-suitable-agent'
                    break

                agent = selected.agent
                attempted_ids.add(agent.agent_id)
                checkpoint.current_agent_id = agent.agent_id
                checkpoint.status = 'running' if attempt == 1 else 'recovering'
                self._save(checkpoint)

                idempotency_key = f'{checkpoint.workflow_id}:{step.step_id}'
                context = {
                    'mode': 'durable-workflow',
                    'workflow_id': checkpoint.workflow_id,
                    'step_id': step.step_id,
                    'step_index': step_index,
                    'attempt': attempt,
                    'idempotency_key': idempotency_key,
                    'checkpoint_version': checkpoint.version,
                    'completed_steps': [
                        {
                            'step_id': item['step_id'],
                            'agent_id': item['agent_id'],
                            'response': item.get('response'),
                        }
                        for item in checkpoint.completed_steps
                    ],
                    'step_metadata': step.metadata,
                }

                try:
                    response = await self.a2a.invoke(agent, step.task, context=context)
                except Exception as exc:
                    last_error = str(exc)
                    failure = {
                        'step_id': step.step_id,
                        'step_index': step_index,
                        'agent_id': agent.agent_id,
                        'attempt': attempt,
                        'error': last_error,
                    }
                    checkpoint.failed_attempts.append(failure)
                    checkpoint.current_agent_id = None
                    checkpoint.status = 'recovering'
                    self._record_outcome(
                        agent,
                        False,
                        {
                            'phase': 'durable-workflow-step',
                            'workflow_id': checkpoint.workflow_id,
                            'step_id': step.step_id,
                            'attempt': attempt,
                            'error': last_error,
                        },
                    )
                    self._save(checkpoint)
                    if self.observability:
                        self.observability.audit.record(
                            'workflow.step.failed',
                            agent.agent_id,
                            workflow_id=checkpoint.workflow_id,
                            step_id=step.step_id,
                            attempt=attempt,
                            error=last_error,
                        )
                        self.observability.metrics.inc('workflow_step_attempts_total', status='failed')
                    continue

                completed = {
                    'step_id': step.step_id,
                    'step_index': step_index,
                    'agent_id': agent.agent_id,
                    'attempt': attempt,
                    'recovered': attempt > 1,
                    'idempotency_key': idempotency_key,
                    'response': response,
                }
                checkpoint.completed_steps.append(completed)
                checkpoint.next_step_index += 1
                checkpoint.current_agent_id = None
                checkpoint.status = 'completed' if checkpoint.next_step_index == len(steps) else 'running'
                self._record_outcome(
                    agent,
                    True,
                    {
                        'phase': 'durable-workflow-step',
                        'workflow_id': checkpoint.workflow_id,
                        'step_id': step.step_id,
                        'attempt': attempt,
                        'recovered': attempt > 1,
                    },
                )
                # Critical durability boundary: persist completion before moving on.
                self._save(checkpoint)
                if self.observability:
                    self.observability.audit.record(
                        'workflow.step.completed',
                        agent.agent_id,
                        workflow_id=checkpoint.workflow_id,
                        step_id=step.step_id,
                        attempt=attempt,
                    )
                    self.observability.metrics.inc('workflow_step_attempts_total', status='success')
                break
            else:
                last_error = last_error or 'failover-budget-exhausted'

            if checkpoint.next_step_index == step_index:
                checkpoint.status = 'failed'
                checkpoint.current_agent_id = None
                checkpoint.failed_attempts.append({
                    'step_id': step.step_id,
                    'step_index': step_index,
                    'agent_id': None,
                    'attempt': max_failovers + 1,
                    'error': last_error or 'failover-budget-exhausted',
                    'terminal': True,
                })
                self._save(checkpoint)
                return self._result(checkpoint)

        return self._result(checkpoint)
