from __future__ import annotations

from typing import Any, Mapping, Sequence

from .model_adapters import ModelAdapter
from .orchestrator import AgentWeave
from .tool_routing import ToolRouter


class BYOMAgentWeave(AgentWeave):
    """AgentWeave with a user-supplied model and tool catalog.

    This facade leaves the existing A2A ``solve`` path unchanged and adds a
    model-agnostic ``run`` path for function/tool-calling applications.
    """

    def __init__(
        self,
        *args: Any,
        model: ModelAdapter | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_router: ToolRouter | None = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.model = model
        self.tools = list(tools or [])
        self.tool_router = tool_router or ToolRouter(self.analyzer)

    def set_model(self, model: ModelAdapter) -> "BYOMAgentWeave":
        self.model = model
        return self

    def set_tools(self, tools: Sequence[Mapping[str, Any]]) -> "BYOMAgentWeave":
        self.tools = list(tools)
        return self

    def route_tools(
        self,
        text: str,
        *,
        tools: Sequence[Mapping[str, Any]] | None = None,
        max_tools: int = 8,
    ):
        return self.tool_router.route(text, self.tools if tools is None else tools, max_tools=max_tools)

    async def run(
        self,
        text: str,
        *,
        model: ModelAdapter | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        max_tools: int = 8,
        messages: Sequence[Mapping[str, Any]] | None = None,
        model_kwargs: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        active_model = model or self.model
        if active_model is None:
            raise ValueError("No model configured. Pass model=... or call set_model(...).")

        active_tools = self.tools if tools is None else list(tools)
        routing = self.tool_router.route(text, active_tools, max_tools=max_tools)
        model_messages = list(messages or [{"role": "user", "content": text}])

        with self.observability.tracer.span(
            "agentweave.model.invoke",
            model=active_model.identity,
            tools_before=len(active_tools),
            tools_after=len(routing.selected),
        ):
            response = await active_model.complete(
                model_messages,
                tools=routing.selected,
                **dict(model_kwargs or {}),
            )

        provenance = dict(routing.provenance)
        provenance["model_adapter"] = active_model.identity
        self.observability.audit.record("tool-routing.completed", payload=provenance)
        self.observability.metrics.inc("model_invocations_total", model=active_model.identity)

        return {
            "status": "completed",
            "model": active_model.identity,
            "response": response,
            "selected_tools": routing.selected,
            "filtered_tools": routing.filtered,
            "routing_provenance": provenance,
            "observability": self.observability.snapshot(),
        }
