from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ToolSpec:
    """Provider-neutral tool descriptor used throughout the AgentWeave runtime."""

    name: str
    description: str = ""
    input_schema: Mapping[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )
    id: str | None = None
    provider: str | None = None
    source: str | None = None
    model_name: str | None = None
    risk_level: str = "standard"
    permissions: frozenset[str] = frozenset()
    scopes: frozenset[str] = frozenset()
    roles: frozenset[str] = frozenset()
    tenants: frozenset[str] = frozenset()
    environments: frozenset[str] = frozenset()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    idempotency: str = "auto"
    native: Any = field(default=None, compare=False, repr=False)

    @property
    def key(self) -> str:
        """Stable runtime identity; independent from the model-visible function name."""
        if self.id:
            return str(self.id)
        parts = [self.provider or "tool", self.source or "local", self.name]
        return ":".join(str(part) for part in parts)

    @property
    def exposed_name(self) -> str:
        """Function name shown to the model."""
        return self.model_name or self.name

    def to_function_tool(self) -> dict[str, Any]:
        """Return an OpenAI-compatible function-tool descriptor."""
        return {
            "type": "function",
            "function": {
                "name": self.exposed_name,
                "description": self.description,
                "parameters": dict(self.input_schema),
            },
        }


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    id: str | None = None
    provider: str | None = None
    model_name: str | None = None
    tool_key: str | None = None
    parse_error: str | None = None
    raw: Any = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str | None
    name: str
    success: bool
    content: Any = None
    structured_content: Any = None
    error: str | None = None
    model_name: str | None = None
    tool_key: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    raw: Any = field(default=None, compare=False, repr=False)

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

    def model_content(self) -> str:
        value = self.structured_content
        if value is None:
            value = self.content
        if value is None and self.error:
            value = {"error": self.error}
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (Mapping, list, tuple, bool, int, float)):
            return self._canonical_json(value)
        return str(value)


@dataclass(frozen=True)
class ModelResponse:
    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)
    raw: Any = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class RunContext:
    """Security and tenancy context carried through every runtime stage."""

    identity: str | None = None
    role: str | None = None
    tenant: str | None = None
    permissions: frozenset[str] = frozenset()
    scopes: frozenset[str] = frozenset()
    environment: str | None = None
    risk_tier: str = "standard"
    human_approved: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeStageEvent:
    stage: str
    duration_ms: float
    outcome: str = "ok"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeTelemetry:
    """Per-run runtime telemetry without coupling AgentWeave to one exporter."""

    events: list[RuntimeStageEvent] = field(default_factory=list)

    def record(
        self,
        stage: str,
        duration_ms: float,
        *,
        outcome: str = "ok",
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.events.append(
            RuntimeStageEvent(
                stage=stage,
                duration_ms=float(duration_ms),
                outcome=outcome,
                metadata=dict(metadata or {}),
            )
        )

    def as_dict(self) -> dict[str, Any]:
        totals: dict[str, float] = {}
        for event in self.events:
            totals[event.stage] = totals.get(event.stage, 0.0) + event.duration_ms
        return {
            "events": [
                {
                    "stage": event.stage,
                    "duration_ms": event.duration_ms,
                    "outcome": event.outcome,
                    "metadata": dict(event.metadata),
                }
                for event in self.events
            ],
            "stage_totals_ms": totals,
            "total_ms": sum(event.duration_ms for event in self.events),
        }


@dataclass(frozen=True)
class RuntimeResult:
    status: str
    response: ModelResponse | None
    tool_results: tuple[ToolResult, ...]
    selected_tools: tuple[str, ...]
    routing_confidence: float | None = None
    routing_abstained: bool = False
    recovery_attempts: int = 0
    provenance: Mapping[str, Any] = field(default_factory=dict)
    telemetry: Mapping[str, Any] = field(default_factory=dict)
