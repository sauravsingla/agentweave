from __future__ import annotations

"""A2A TCK compatibility entrypoint kept outside the frozen router scope.

The untouched-generalization protocol freezes every file under ``agentweave/``.
Protocol-conformance shims therefore live here so A2A TCK compatibility can
advance without mutating the frozen research implementation.
"""

import os

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.request_handlers.request_handler import validate, validate_request_params
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, TaskState
from a2a.utils.errors import TaskNotFoundError, UnsupportedOperationError
from starlette.applications import Starlette

from agentweave.a2a_server import AgentWeaveTCKExecutor, JsonRpcContentTypeMiddleware


TERMINAL_TASK_STATES = {
    TaskState.TASK_STATE_COMPLETED,
    TaskState.TASK_STATE_FAILED,
    TaskState.TASK_STATE_CANCELED,
    TaskState.TASK_STATE_REJECTED,
}


class TCKRequestHandler(DefaultRequestHandler):
    """Map terminal-task subscriptions to the A2A-required error code."""

    @validate_request_params
    @validate(
        lambda self: self._agent_card.capabilities.streaming,
        "Streaming is not supported by the agent",
    )
    async def on_subscribe_to_task(self, params, context):
        task = await self.task_store.get(params.id, context)
        if task is None:
            raise TaskNotFoundError
        if task.status.state in TERMINAL_TASK_STATES:
            raise UnsupportedOperationError(
                "Cannot subscribe to a task in a terminal state"
            )
        async for event in super().on_subscribe_to_task(params, context):
            yield event


def build_app(base_url: str = "http://127.0.0.1:9998") -> Starlette:
    skill = AgentSkill(
        id="agentweave_interop",
        name="AgentWeave interoperability",
        description="A deterministic AgentWeave endpoint for A2A conformance and lifecycle testing.",
        input_modes=["text/plain"],
        output_modes=["text/plain"],
        tags=["agentweave", "a2a", "tck"],
        examples=["hello"],
    )
    card = AgentCard(
        name="AgentWeave TCK Agent",
        description="AgentWeave A2A protocol conformance endpoint",
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=True, extended_agent_card=False),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url=base_url,
                protocol_version="1.0",
            )
        ],
        skills=[skill],
    )
    handler = TCKRequestHandler(
        agent_executor=AgentWeaveTCKExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = []
    routes.extend(create_agent_card_routes(card))
    routes.extend(create_jsonrpc_routes(handler, "/"))
    app = Starlette(routes=routes)
    app.add_middleware(JsonRpcContentTypeMiddleware)
    return app


def main() -> None:
    host = os.getenv("AGENTWEAVE_TCK_HOST", "127.0.0.1")
    port = int(os.getenv("AGENTWEAVE_TCK_PORT", "9998"))
    uvicorn.run(build_app(f"http://{host}:{port}"), host=host, port=port)


if __name__ == "__main__":
    main()
