from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable

from agentweave_security.scope_filter import (
    ScopeContext,
    ScopedTool,
    StaticScopeFilter,
    apply_policy_then_optional_routing,
)


class ScopeBenchmarkCondition(str, Enum):
    ALL_TOOLS = "all_tools"
    POLICY_ONLY = "policy_only"
    POLICY_PLUS_ROUTING = "policy_plus_routing"


@dataclass(frozen=True)
class ScopeBenchmarkOutcome:
    condition: ScopeBenchmarkCondition
    catalog_total: int
    model_visible_candidates: int
    policy_denied_visible: int
    relevant_visible: int
    task_success: bool
    candidate_reduction_pct: float
    input_token_proxy: int
    policy_latency_ms: float
    routing_latency_ms: float
    model_latency_ms: float
    total_latency_ms: float

    def to_dict(self) -> dict:
        row = asdict(self)
        row["condition"] = self.condition.value
        return row


def default_scope_catalog() -> tuple[ScopedTool, ...]:
    return (
        ScopedTool("lookup", roles=frozenset({"analyst"}), permissions=frozenset({"read"}), metadata={"relevant": True}),
        ScopedTool("verify", roles=frozenset({"analyst"}), permissions=frozenset({"read"}), metadata={"relevant": False}),
        ScopedTool("admin_export", roles=frozenset({"admin"}), permissions=frozenset({"export"}), metadata={"relevant": False}),
        ScopedTool("tenant_b_report", tenants=frozenset({"tenant-b"}), metadata={"relevant": False}),
        ScopedTool("dev_console", environments=frozenset({"dev"}), metadata={"relevant": False}),
        ScopedTool("public_help", metadata={"relevant": False}),
    )


def _is_relevant(tool: ScopedTool) -> bool:
    return bool((tool.metadata or {}).get("relevant", False))


def _task_success(visible: tuple[ScopedTool, ...]) -> bool:
    return any(tool.name == "lookup" for tool in visible)


def run_scope_benchmark(condition: ScopeBenchmarkCondition) -> ScopeBenchmarkOutcome:
    catalog = default_scope_catalog()
    context = ScopeContext(
        role="analyst",
        tenant="tenant-a",
        permissions=frozenset({"read"}),
        environment="prod",
    )
    scope_filter = StaticScopeFilter(policy_version="benchmark-policy-v1")
    policy_latency = 0.5
    routing_latency = 0.0

    if condition is ScopeBenchmarkCondition.ALL_TOOLS:
        visible = catalog
        denied_names: set[str] = set()
    elif condition is ScopeBenchmarkCondition.POLICY_ONLY:
        filtered = scope_filter.filter(catalog, context)
        visible = filtered.tools
        denied_names = {decision.tool for decision in filtered.dropped}
    else:
        denied_names = {
            decision.tool
            for decision in scope_filter.filter(catalog, context).dropped
        }

        def router(tools):
            return tuple(tool for tool in tools if _is_relevant(tool))

        result = apply_policy_then_optional_routing(
            tools=catalog,
            context=context,
            scope_filter=scope_filter,
            router=router,
            router_version="benchmark-router-v1",
        )
        visible = result.model_visible_tools
        routing_latency = 1.5

    base_tokens = 80
    tokens_per_candidate = 32
    input_tokens = base_tokens + tokens_per_candidate * len(visible)
    model_latency = 5.0 + 0.4 * len(visible)
    total_latency = model_latency
    if condition is not ScopeBenchmarkCondition.ALL_TOOLS:
        total_latency += policy_latency
    total_latency += routing_latency

    reduction = 100.0 * (1.0 - len(visible) / len(catalog))
    return ScopeBenchmarkOutcome(
        condition=condition,
        catalog_total=len(catalog),
        model_visible_candidates=len(visible),
        policy_denied_visible=sum(tool.name in denied_names for tool in visible),
        relevant_visible=sum(_is_relevant(tool) for tool in visible),
        task_success=_task_success(visible),
        candidate_reduction_pct=reduction,
        input_token_proxy=input_tokens,
        policy_latency_ms=0.0 if condition is ScopeBenchmarkCondition.ALL_TOOLS else policy_latency,
        routing_latency_ms=routing_latency,
        model_latency_ms=model_latency,
        total_latency_ms=total_latency,
    )


def run_scope_benchmark_comparison() -> list[ScopeBenchmarkOutcome]:
    return [run_scope_benchmark(condition) for condition in ScopeBenchmarkCondition]


def summarize_scope_benchmark(outcomes: Iterable[ScopeBenchmarkOutcome]) -> dict:
    rows = list(outcomes)
    return {
        "runs": len(rows),
        "task_successes": sum(row.task_success for row in rows),
        "by_condition": {row.condition.value: row.to_dict() for row in rows},
    }
