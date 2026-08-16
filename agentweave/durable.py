from __future__ import annotations

from .orchestrator import AgentWeave
from .workflow import DurableWorkflowEngine


class DurableAgentWeave(AgentWeave):
    """AgentWeave with persistent multi-step workflow execution and resume APIs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflows = DurableWorkflowEngine(
            self.a2a,
            self.matcher,
            self.trust,
            self.registry,
            self.store,
            self.register,
            self.observability,
        )

    async def run_workflow(self, steps, *, workflow_id=None, max_failovers=2):
        return await self.workflows.start(
            steps,
            workflow_id=workflow_id,
            max_failovers=max_failovers,
        )

    async def resume_workflow(self, workflow_id, *, max_failovers=2):
        return await self.workflows.resume(workflow_id, max_failovers=max_failovers)

    def workflow_state(self, workflow_id):
        state = self.workflows.state(workflow_id)
        return state.to_dict() if state else None

    def workflow_states(self, limit=100):
        return [state.to_dict() for state in self.workflows.list_states(limit=limit)]
