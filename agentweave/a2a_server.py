from __future__ import annotations

"""Reference AgentWeave A2A server used for protocol conformance tests.

This module intentionally uses the official Python A2A SDK so AgentWeave can be
exercised as a System Under Test by the Linux Foundation A2A TCK.
"""

from a2a.helpers import (
    get_message_text,
    new_data_part,
    new_raw_part,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
    new_url_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.request_handlers.request_handler import validate, validate_request_params
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, TaskState
from a2a.utils.errors import TaskNotFoundError, UnsupportedOperationError
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


TERMINAL_TASK_STATES = {
    TaskState.TASK_STATE_COMPLETED,
    TaskState.TASK_STATE_FAILED,
    TaskState.TASK_STATE_CANCELED,
    TaskState.TASK_STATE_REJECTED,
}


class JsonRpcContentTypeMiddleware(BaseHTTPMiddleware):
    """Reject invalid JSON-RPC media types before body parsing."""
    async def dispatch(self, request, call_next):
        if request.method == 'POST' and request.url.path in {'', '/'}:
            content_type=request.headers.get('content-type','').lower()
            if not content_type.startswith('application/json'):
                return Response(status_code=415)
        return await call_next(request)


class AgentWeaveRequestHandler(DefaultRequestHandler):
    """A2A handler with explicit terminal-task subscription semantics."""

    @validate_request_params
    @validate(
        lambda self: self._agent_card.capabilities.streaming,
        'Streaming is not supported by the agent',
    )
    async def on_subscribe_to_task(self, params, context):
        task = await self.task_store.get(params.id, context)
        if task is None:
            raise TaskNotFoundError
        if task.status.state in TERMINAL_TASK_STATES:
            raise UnsupportedOperationError(
                'Cannot subscribe to a task in a terminal state'
            )
        async for event in super().on_subscribe_to_task(params, context):
            yield event


class AgentWeaveTCKExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message_id=str(getattr(context.message,'message_id','') or '')

        # The TCK has a MUST case where SendMessage returns a Message directly.
        if 'message-response' in message_id:
            await event_queue.enqueue_event(new_text_message('Direct message response'))
            return

        task=context.current_task or new_task_from_user_message(context.message)
        if context.current_task is None:
            await event_queue.enqueue_event(task)
        updater=TaskUpdater(event_queue=event_queue,task_id=task.id,context_id=task.context_id)
        await updater.update_status(TaskState.TASK_STATE_WORKING,new_text_message('AgentWeave is processing the request.'))

        # Keep prerequisite tasks non-terminal so GetTask/CancelTask/history tests
        # can exercise the full protocol lifecycle.
        if 'input-required' in message_id:
            await updater.update_status(
                TaskState.TASK_STATE_INPUT_REQUIRED,
                new_text_message('Additional input is required.'),
            )
            return

        if 'artifact-file-url' in message_id:
            parts=[new_url_part('https://example.com/output.txt',media_type='text/plain',filename='output.txt')]
        elif 'artifact-file' in message_id:
            parts=[new_raw_part(b'Generated file content',media_type='text/plain',filename='output.txt')]
        elif 'artifact-data' in message_id:
            parts=[new_data_part({'key':'value','count':42},media_type='application/json')]
        elif 'artifact-text' in message_id:
            parts=[new_text_part('Generated text content',media_type='text/plain')]
        else:
            query=get_message_text(context.message) or ''
            parts=[new_text_part(text=f'AgentWeave acknowledgement: {query}',media_type='text/plain')]

        await updater.add_artifact(parts=parts)
        await updater.update_status(TaskState.TASK_STATE_COMPLETED,new_text_message('AgentWeave request completed.'))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task=context.current_task
        if task is None:
            raise ValueError('No current task to cancel')
        updater=TaskUpdater(event_queue=event_queue,task_id=task.id,context_id=task.context_id)
        await updater.update_status(TaskState.TASK_STATE_CANCELED,new_text_message('AgentWeave task canceled.'))


def build_app(base_url='http://127.0.0.1:9998'):
    skill=AgentSkill(
        id='agentweave_interop',
        name='AgentWeave interoperability',
        description='A deterministic AgentWeave endpoint for A2A conformance and lifecycle testing.',
        input_modes=['text/plain'],output_modes=['text/plain'],tags=['agentweave','a2a','tck'],examples=['hello'],
    )
    card=AgentCard(
        name='AgentWeave TCK Agent',description='AgentWeave A2A protocol conformance endpoint',version='1.0.0',
        default_input_modes=['text/plain'],default_output_modes=['text/plain'],
        capabilities=AgentCapabilities(streaming=True,extended_agent_card=False),
        supported_interfaces=[AgentInterface(protocol_binding='JSONRPC',url=base_url,protocol_version='1.0')],
        skills=[skill],
    )
    handler=AgentWeaveRequestHandler(agent_executor=AgentWeaveTCKExecutor(),task_store=InMemoryTaskStore(),agent_card=card)
    routes=[]; routes.extend(create_agent_card_routes(card)); routes.extend(create_jsonrpc_routes(handler,'/'))
    app=Starlette(routes=routes)
    app.add_middleware(JsonRpcContentTypeMiddleware)
    return app


def main():
    import os, uvicorn
    host=os.getenv('AGENTWEAVE_TCK_HOST','127.0.0.1'); port=int(os.getenv('AGENTWEAVE_TCK_PORT','9998'))
    uvicorn.run(build_app(f'http://{host}:{port}'),host=host,port=port)


if __name__=='__main__': main()
