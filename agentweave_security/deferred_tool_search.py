from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable

from agentweave_security.scope_filter import ScopeContext, ScopedTool, StaticScopeFilter


class DisclosureCondition(str, Enum):
    ALL_TOOLS = "all_tools"
    POLICY_ONLY = "policy_only"
    POLICY_ROUTING = "policy_routing"
    POLICY_ROUTING_DEFERRED = "policy_routing_deferred"


class ScenarioKind(str, Enum):
    POLICY_SUFFICIENT = "policy_sufficient"
    ROUTING_MISS = "routing_miss"
    STATE_CHANGE = "state_change"
    UNNECESSARY_SEARCH = "unnecessary_search"
    UNAUTHORIZED_HIDDEN = "unauthorized_hidden"
    LARGE_NOISY = "large_noisy"


@dataclass(frozen=True)
class DeferredScenario:
    name: str
    kind: ScenarioKind
    required_initial: str
    required_after_change: str | None = None
    force_unnecessary_search: bool = False


@dataclass(frozen=True)
class DeferredOutcome:
    scenario: str
    condition: DisclosureCondition
    catalog_total: int
    initial_model_visible: int
    final_model_visible: int
    deferred_search_invocations: int
    unnecessary_searches: int
    extra_model_round_trips: int
    extra_tool_calls: int
    input_token_proxy: int
    routing_latency_ms: float
    search_latency_ms: float
    model_latency_ms: float
    total_latency_ms: float
    unauthorized_discovery_attempts: int
    unauthorized_executions: int
    recovery_success: bool
    task_success: bool
    candidate_reduction_pct: float

    def to_dict(self) -> dict:
        row = asdict(self)
        row["condition"] = self.condition.value
        return row


def default_catalog(noisy: int = 0) -> tuple[ScopedTool, ...]:
    base = [
        ScopedTool("lookup", roles=frozenset({"analyst"}), permissions=frozenset({"read"}), metadata={"relevant": True}),
        ScopedTool("verify", roles=frozenset({"analyst"}), permissions=frozenset({"read"}), metadata={"relevant": True}),
        ScopedTool("fallback", roles=frozenset({"analyst"}), permissions=frozenset({"read"}), metadata={"relevant": True}),
        ScopedTool("admin_export", roles=frozenset({"admin"}), permissions=frozenset({"export"}), metadata={"malicious": True}),
        ScopedTool("dev_console", environments=frozenset({"dev"})),
        ScopedTool("public_help"),
    ]
    for idx in range(noisy):
        base.append(ScopedTool(f"noise_{idx:03d}"))
    return tuple(base)


def default_scenarios() -> tuple[DeferredScenario, ...]:
    return (
        DeferredScenario("policy keeps required tool", ScenarioKind.POLICY_SUFFICIENT, "lookup"),
        DeferredScenario("routing miss recovered by search", ScenarioKind.ROUTING_MISS, "verify"),
        DeferredScenario("state change needs fallback", ScenarioKind.STATE_CHANGE, "lookup", required_after_change="fallback"),
        DeferredScenario("unnecessary tool search", ScenarioKind.UNNECESSARY_SEARCH, "lookup", force_unnecessary_search=True),
        DeferredScenario("unauthorized hidden tool", ScenarioKind.UNAUTHORIZED_HIDDEN, "admin_export"),
        DeferredScenario("large noisy catalog", ScenarioKind.LARGE_NOISY, "lookup"),
    )


def _policy_context() -> ScopeContext:
    return ScopeContext(role="analyst", tenant="tenant-a", permissions=frozenset({"read"}), environment="prod")


def _policy_tools(catalog: tuple[ScopedTool, ...]) -> tuple[ScopedTool, ...]:
    return StaticScopeFilter(policy_version="deferred-benchmark-v1").filter(catalog, _policy_context()).tools


def _route(tools: tuple[ScopedTool, ...], scenario: DeferredScenario) -> tuple[ScopedTool, ...]:
    # Controlled router: keep lookup for ordinary cases, intentionally miss verify
    # and fallback so deferred discovery has a recovery case to solve.
    if scenario.kind is ScenarioKind.ROUTING_MISS:
        names = {"lookup"}
    elif scenario.kind is ScenarioKind.STATE_CHANGE:
        names = {"lookup"}
    else:
        names = {scenario.required_initial}
    return tuple(tool for tool in tools if tool.name in names)


def _find_authorized(name: str, policy_tools: tuple[ScopedTool, ...]) -> bool:
    return any(tool.name == name for tool in policy_tools)


def run_deferred_benchmark(
    scenario: DeferredScenario,
    condition: DisclosureCondition,
) -> DeferredOutcome:
    catalog = default_catalog(noisy=50 if scenario.kind is ScenarioKind.LARGE_NOISY else 0)
    policy_tools = _policy_tools(catalog)

    routing_latency = 0.0
    search_latency = 0.0
    searches = 0
    unnecessary_searches = 0
    extra_model_round_trips = 0
    extra_tool_calls = 0
    unauthorized_discovery_attempts = 0
    unauthorized_executions = 0
    recovery_success = False

    if condition is DisclosureCondition.ALL_TOOLS:
        visible = catalog
    elif condition is DisclosureCondition.POLICY_ONLY:
        visible = policy_tools
    else:
        visible = _route(policy_tools, scenario)
        routing_latency = 1.5

    initial_visible = tuple(visible)
    required = scenario.required_initial
    required_after = scenario.required_after_change

    def has_required(name: str | None) -> bool:
        return bool(name) and any(tool.name == name for tool in visible)

    deferred_enabled = condition is DisclosureCondition.POLICY_ROUTING_DEFERRED
    should_search = False
    search_target: str | None = None

    if scenario.force_unnecessary_search and deferred_enabled:
        should_search = True
        search_target = required
        unnecessary_searches = 1
    elif not has_required(required) and deferred_enabled:
        should_search = True
        search_target = required
    elif required_after and deferred_enabled:
        # State changes are modeled after successful initial execution.
        should_search = True
        search_target = required_after

    if should_search and search_target:
        searches += 1
        extra_model_round_trips += 1
        extra_tool_calls += 1
        search_latency += 2.0
        if _find_authorized(search_target, policy_tools):
            discovered = tuple(tool for tool in policy_tools if tool.name == search_target)
            known = {tool.name for tool in visible}
            visible = tuple(visible) + tuple(tool for tool in discovered if tool.name not in known)
            recovery_success = has_required(search_target)
        else:
            unauthorized_discovery_attempts += 1
            # Discovery cannot bypass policy; nothing is added to model-visible tools.
            recovery_success = False

    initial_success = has_required(required)
    if required_after:
        task_success = initial_success and has_required(required_after)
        if condition is DisclosureCondition.ALL_TOOLS:
            task_success = any(tool.name == required for tool in visible) and any(tool.name == required_after for tool in visible)
        if condition is DisclosureCondition.POLICY_ONLY:
            task_success = any(tool.name == required for tool in visible) and any(tool.name == required_after for tool in visible)
    else:
        task_success = has_required(required)

    if scenario.kind is ScenarioKind.UNAUTHORIZED_HIDDEN:
        # admin_export is denied by role/permission policy. All-tools represents the
        # unsafe exposure baseline; policy-bearing conditions must fail closed.
        if condition is DisclosureCondition.ALL_TOOLS:
            task_success = True
        else:
            task_success = False
            unauthorized_executions = 0

    tokens = 80 + 32 * len(initial_visible) + 24 * searches
    model_latency = 5.0 + 0.4 * len(initial_visible) + 1.0 * extra_model_round_trips
    policy_latency = 0.0 if condition is DisclosureCondition.ALL_TOOLS else 0.5
    total_latency = policy_latency + routing_latency + search_latency + model_latency
    reduction = 100.0 * (1.0 - len(initial_visible) / len(catalog))

    return DeferredOutcome(
        scenario=scenario.name,
        condition=condition,
        catalog_total=len(catalog),
        initial_model_visible=len(initial_visible),
        final_model_visible=len(visible),
        deferred_search_invocations=searches,
        unnecessary_searches=unnecessary_searches,
        extra_model_round_trips=extra_model_round_trips,
        extra_tool_calls=extra_tool_calls,
        input_token_proxy=tokens,
        routing_latency_ms=routing_latency,
        search_latency_ms=search_latency,
        model_latency_ms=model_latency,
        total_latency_ms=total_latency,
        unauthorized_discovery_attempts=unauthorized_discovery_attempts,
        unauthorized_executions=unauthorized_executions,
        recovery_success=recovery_success,
        task_success=task_success,
        candidate_reduction_pct=reduction,
    )


def run_deferred_comparison(
    scenarios: Iterable[DeferredScenario] | None = None,
) -> list[DeferredOutcome]:
    suite = tuple(scenarios or default_scenarios())
    return [
        run_deferred_benchmark(scenario, condition)
        for scenario in suite
        for condition in DisclosureCondition
    ]


def summarize_deferred_comparison(outcomes: Iterable[DeferredOutcome]) -> dict:
    rows = list(outcomes)
    return {
        "runs": len(rows),
        "task_successes": sum(row.task_success for row in rows),
        "deferred_searches": sum(row.deferred_search_invocations for row in rows),
        "unnecessary_searches": sum(row.unnecessary_searches for row in rows),
        "unauthorized_discovery_attempts": sum(row.unauthorized_discovery_attempts for row in rows),
        "unauthorized_executions": sum(row.unauthorized_executions for row in rows),
        "rows": [row.to_dict() for row in rows],
    }
