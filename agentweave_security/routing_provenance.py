from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Iterable, Mapping

from agentweave_security.authorization import StageTelemetry
from agentweave_security.scope_filter import PolicyRoutingResult, ScopedTool


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ModelCallRecord:
    selected_action: str | None
    arguments: Mapping[str, object] | None = None
    call_id: str | None = None


@dataclass(frozen=True)
class ExecutionRecord:
    attempted: bool
    authorized: bool | None
    authorization_reason: str | None
    executed: bool
    success: bool | None
    result_code: str | None = None
    recovery_attempted: bool = False
    recovery_success: bool | None = None


@dataclass(frozen=True)
class ToolRoutingProvenance:
    schema_version: str
    source_catalog: tuple[str, ...]
    source_catalog_hash: str
    policy_version: str | None
    policy_context_fingerprint: str | None
    policy_filtered_out: tuple[str, ...]
    policy_filter_reasons: Mapping[str, str]
    policy_permitted: tuple[str, ...]
    router_applied: bool
    router_version: str | None
    router_filtered_out: tuple[str, ...]
    model_visible_tools: tuple[str, ...]
    model_call: ModelCallRecord
    execution: ExecutionRecord
    stage_telemetry: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        row = asdict(self)
        row["policy_filter_reasons"] = dict(self.policy_filter_reasons)
        row["stage_telemetry"] = dict(self.stage_telemetry)
        return row

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def record_hash(self) -> str:
        return _stable_hash(self.to_dict())


def build_tool_routing_provenance(
    *,
    source_tools: Iterable[ScopedTool],
    routing_result: PolicyRoutingResult,
    model_call: ModelCallRecord,
    execution: ExecutionRecord,
    telemetry: StageTelemetry | None = None,
    schema_version: str = "tool-routing-provenance-v1",
) -> ToolRoutingProvenance:
    """Build a portable decision record without exposing private reasoning traces."""
    source = tuple(tool.name for tool in source_tools)
    permitted = tuple(tool.name for tool in routing_result.policy_tools)
    visible = tuple(tool.name for tool in routing_result.model_visible_tools)
    decisions = {decision.tool: decision for decision in routing_result.decisions}
    policy_filtered = tuple(name for name in source if name not in set(permitted))
    routing_filtered = tuple(name for name in permitted if name not in set(visible))

    return ToolRoutingProvenance(
        schema_version=schema_version,
        source_catalog=source,
        source_catalog_hash=routing_result.provenance.source_catalog_hash,
        policy_version=routing_result.provenance.policy_version,
        policy_context_fingerprint=routing_result.provenance.context_fingerprint,
        policy_filtered_out=policy_filtered,
        policy_filter_reasons={name: decisions[name].reason_code for name in policy_filtered},
        policy_permitted=permitted,
        router_applied=routing_result.router_applied,
        router_version=routing_result.provenance.router_version,
        router_filtered_out=routing_filtered,
        model_visible_tools=visible,
        model_call=model_call,
        execution=execution,
        stage_telemetry={} if telemetry is None else telemetry.as_dict(),
    )
