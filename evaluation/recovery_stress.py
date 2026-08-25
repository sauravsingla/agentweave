from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable


class RecoveryCondition(str, Enum):
    FIXED_ROUTED_SET = "fixed_routed_set"
    REROUTE_ON_CHANGE = "reroute_on_change"
    ALL_TOOLS = "all_tools"


@dataclass(frozen=True)
class StressScenario:
    name: str
    initial_required_capability: str
    initial_routed_capabilities: tuple[str, ...]
    changed_required_capability: str
    available_capabilities: tuple[str, ...]
    selected_tool_fails: bool = False
    base_model_calls: int = 1
    base_tool_calls: int = 1
    base_latency_ms: float = 10.0
    base_input_tokens: int = 100


@dataclass(frozen=True)
class RecoveryStressOutcome:
    scenario: str
    condition: RecoveryCondition
    required_tool_survived_initially: bool
    required_tool_survived_after_change: bool
    rerouting_events: int
    recovery_success: bool
    extra_model_calls: int
    extra_tool_calls: int
    latency_overhead_ms: float
    token_overhead: int
    final_task_success: bool

    def to_dict(self) -> dict:
        row = asdict(self)
        row["condition"] = self.condition.value
        return row


def run_stress_scenario(
    scenario: StressScenario,
    condition: RecoveryCondition,
    *,
    reroute_latency_ms: float = 3.0,
    reroute_token_cost: int = 24,
) -> RecoveryStressOutcome:
    """Run a deterministic controlled recovery/state-change scenario.

    This evaluation harness intentionally lives outside the frozen AgentWeave
    runtime. It compares exposure policies without modifying historical BFCL
    scores or router code.
    """
    initial = set(scenario.initial_routed_capabilities)
    available = set(scenario.available_capabilities)
    initial_required = scenario.initial_required_capability
    changed_required = scenario.changed_required_capability

    if condition is RecoveryCondition.ALL_TOOLS:
        visible = set(available)
    else:
        visible = set(initial)

    initial_survival = initial_required in visible
    changed_survival_before_recovery = changed_required in visible

    rerouting_events = 0
    extra_model_calls = 0
    extra_tool_calls = 0
    latency_overhead_ms = 0.0
    token_overhead = 0
    recovery_success = False

    needs_recovery = scenario.selected_tool_fails or not changed_survival_before_recovery

    if needs_recovery and condition is RecoveryCondition.REROUTE_ON_CHANGE:
        rerouting_events = 1
        extra_model_calls = 1
        extra_tool_calls = 1
        latency_overhead_ms = reroute_latency_ms
        token_overhead = reroute_token_cost
        if changed_required in available:
            visible.add(changed_required)
            recovery_success = True
    elif needs_recovery and condition is RecoveryCondition.ALL_TOOLS:
        # The recovery capability was already model-visible, so no re-routing
        # event is required. A failed tool call still incurs one replacement call.
        extra_tool_calls = 1 if scenario.selected_tool_fails else 0
        recovery_success = changed_required in available

    changed_survival_after_recovery = changed_required in visible

    if condition is RecoveryCondition.FIXED_ROUTED_SET:
        final_success = initial_survival and (not scenario.selected_tool_fails) and changed_survival_after_recovery
    else:
        final_success = initial_survival and changed_survival_after_recovery and (
            not scenario.selected_tool_fails or recovery_success
        )

    return RecoveryStressOutcome(
        scenario=scenario.name,
        condition=condition,
        required_tool_survived_initially=initial_survival,
        required_tool_survived_after_change=changed_survival_after_recovery,
        rerouting_events=rerouting_events,
        recovery_success=recovery_success,
        extra_model_calls=extra_model_calls,
        extra_tool_calls=extra_tool_calls,
        latency_overhead_ms=latency_overhead_ms,
        token_overhead=token_overhead,
        final_task_success=final_success,
    )


def run_comparison(scenario: StressScenario) -> list[RecoveryStressOutcome]:
    return [run_stress_scenario(scenario, condition) for condition in RecoveryCondition]


def summarize_recovery_comparison(outcomes: Iterable[RecoveryStressOutcome]) -> dict:
    rows = list(outcomes)
    return {
        "conditions": len(rows),
        "final_task_successes": sum(row.final_task_success for row in rows),
        "recovery_successes": sum(row.recovery_success for row in rows),
        "rerouting_events": sum(row.rerouting_events for row in rows),
        "extra_model_calls": sum(row.extra_model_calls for row in rows),
        "extra_tool_calls": sum(row.extra_tool_calls for row in rows),
        "latency_overhead_ms": sum(row.latency_overhead_ms for row in rows),
        "token_overhead": sum(row.token_overhead for row in rows),
        "by_condition": {row.condition.value: row.to_dict() for row in rows},
    }
