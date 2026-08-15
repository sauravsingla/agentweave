from __future__ import annotations
import asyncio
from typing import Awaitable, Callable, Any

Handler = Callable[[str], Any | Awaitable[Any]]

class A2AAdapter:
    async def invoke(self, agent_id: str, task: str) -> dict:
        raise NotImplementedError

class InMemoryA2AAdapter(A2AAdapter):
    """Simple local adapter used for tests and demos. Replace with a real A2A client adapter in deployments."""
    def __init__(self):
        self.handlers: dict[str, Handler] = {}
    def register_handler(self, agent_id: str, handler: Handler) -> None:
        self.handlers[agent_id] = handler
    async def invoke(self, agent_id: str, task: str) -> dict:
        if agent_id not in self.handlers:
            raise KeyError(f"No A2A handler registered for {agent_id}")
        result = self.handlers[agent_id](task)
        if asyncio.iscoroutine(result): result = await result
        return result if isinstance(result, dict) else {"result": result}

class HttpA2AAdapter(A2AAdapter):
    """Protocol boundary for a future/production HTTP A2A SDK integration."""
    def __init__(self, client): self.client = client
    async def invoke(self, agent_id: str, task: str) -> dict:
        response = await self.client.send_task(agent_id=agent_id, task=task)
        return response if isinstance(response, dict) else {"result": response}
