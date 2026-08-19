from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable, Mapping, Sequence

import httpx


class ModelAdapter(ABC):
    """Provider-neutral interface for models used behind AgentWeave routing."""

    @property
    def identity(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    async def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Sequence[Mapping[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError


class CallableModelAdapter(ModelAdapter):
    """Wrap any sync/async user SDK call behind the ModelAdapter contract."""

    def __init__(self, fn: Callable[..., Any], *, name: str = "custom-model"):
        self.fn = fn
        self.name = name

    @property
    def identity(self) -> str:
        return self.name

    async def complete(self, messages, *, tools=None, **kwargs):
        result = self.fn(messages=messages, tools=tools, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result


class OpenAICompatibleModelAdapter(ModelAdapter):
    """Adapter for OpenAI-compatible chat-completions endpoints."""

    def __init__(
        self,
        model: str,
        *,
        base_url: str,
        api_key: str | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = 120.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = dict(headers or {})
        self.timeout = timeout

    @property
    def identity(self) -> str:
        return f"openai-compatible:{self.model}"

    async def complete(self, messages, *, tools=None, **kwargs):
        headers = dict(self.headers)
        if self.api_key:
            headers.setdefault("Authorization", f"Bearer {self.api_key}")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [dict(m) for m in messages],
            **kwargs,
        }
        if tools is not None:
            payload["tools"] = [dict(t) for t in tools]
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
