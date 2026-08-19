from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Mapping, Sequence

import httpx


class ModelAdapter(ABC):
    """Provider-neutral interface for models used behind AgentWeave routing.

    AgentWeave owns candidate routing; the adapter owns the model invocation.  This
    keeps routing independent of OpenAI, Anthropic, Gemini, local runtimes, or any
    other model provider.
    """

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
    """Wrap any user SDK/client with a small async-or-sync callable.

    The callable receives ``messages``, ``tools`` and any additional keyword
    arguments. This is the escape hatch for Anthropic, Gemini, custom enterprise
    gateways, Hugging Face pipelines, or any model API that is not OpenAI-shaped.
    """

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
    """Adapter for OpenAI-compatible chat-completions endpoints.

    The endpoint may be hosted by OpenAI, Azure-compatible gateways, vLLM,
    Ollama/OpenAI compatibility mode, llama.cpp servers, or another compatible
    provider. AgentWeave does not require or inspect the model itself.
    """

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
