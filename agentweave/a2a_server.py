from __future__ import annotations

"""Reference AgentWeave A2A server used for protocol conformance tests.

This module intentionally uses the official Python A2A SDK so AgentWeave can be
exercised as a System Under Test by the Linux Foundation A2A TCK.
"""

from a2a.helpers import get_message_text, new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, TaskState
from starlette.applications import Starlette


class AgentWeaveTCKExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task=context.current_task or new_task_from_user_message(context.message)
        if context.current_task is None:
            await event_queue.enqueue_event(task)
        updater=TaskUpdater(event_queue=event_queue,task_id=task.id,context_id=task.context_id)
        await updater.update_status(TaskState.TASK_STATE_WORKING,new_text_message('AgentWeave is processing the request.'))
        query=get_message_text(context.message) or ''
        await updater.add_artifact(parts=[new_text_part(text=f'AgentWeave acknowledgement: {query}',media_type='text/plain')])
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
    handler=DefaultRequestHandler(agent_executor=AgentWeaveTCKExecutor(),task_store=InMemoryTaskStore(),agent_card=card)
    routes=[]; routes.extend(create_agent_card_routes(card)); routes.extend(create_jsonrpc_routes(handler,'/'))
    return Starlette(routes=routes)


def main():
    import os, uvicorn
    host=os.getenv('AGENTWEAVE_TCK_HOST','127.0.0.1'); port=int(os.getenv('AGENTWEAVE_TCK_PORT','9998'))
    uvicorn.run(build_app(f'http://{host}:{port}'),host=host,port=port)


if __name__=='__main__': main()
