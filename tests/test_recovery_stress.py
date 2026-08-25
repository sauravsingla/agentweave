from evaluation.recovery_stress import (
    RecoveryCondition,
    StressScenario,
    run_comparison,
    run_stress_scenario,
    summarize_recovery_comparison,
)


def _state_change_scenario():
    return StressScenario(
        name="state-change-requires-new-capability",
        initial_required_capability="lookup",
        initial_routed_capabilities=("lookup",),
        changed_required_capability="verify",
        available_capabilities=("lookup", "verify", "fallback"),
    )


def _tool_failure_scenario():
    return StressScenario(
        name="selected-tool-fails",
        initial_required_capability="lookup",
        initial_routed_capabilities=("lookup",),
        changed_required_capability="fallback",
        available_capabilities=("lookup", "fallback"),
        selected_tool_fails=True,
    )


def test_state_change_requires_capability_not_initially_selected():
    scenario = _state_change_scenario()

    fixed = run_stress_scenario(scenario, RecoveryCondition.FIXED_ROUTED_SET)
    rerouted = run_stress_scenario(scenario, RecoveryCondition.REROUTE_ON_CHANGE)
    all_tools = run_stress_scenario(scenario, RecoveryCondition.ALL_TOOLS)

    assert fixed.required_tool_survived_initially is True
    assert fixed.required_tool_survived_after_change is False
    assert fixed.final_task_success is False

    assert rerouted.required_tool_survived_after_change is True
    assert rerouted.rerouting_events == 1
    assert rerouted.recovery_success is True
    assert rerouted.final_task_success is True

    assert all_tools.required_tool_survived_after_change is True
    assert all_tools.rerouting_events == 0
    assert all_tools.final_task_success is True


def test_controlled_selected_tool_failure_requires_recovery():
    scenario = _tool_failure_scenario()

    fixed = run_stress_scenario(scenario, RecoveryCondition.FIXED_ROUTED_SET)
    rerouted = run_stress_scenario(scenario, RecoveryCondition.REROUTE_ON_CHANGE)
    all_tools = run_stress_scenario(scenario, RecoveryCondition.ALL_TOOLS)

    assert fixed.final_task_success is False
    assert fixed.recovery_success is False

    assert rerouted.final_task_success is True
    assert rerouted.recovery_success is True
    assert rerouted.extra_model_calls == 1
    assert rerouted.extra_tool_calls == 1
    assert rerouted.latency_overhead_ms > 0
    assert rerouted.token_overhead > 0

    assert all_tools.final_task_success is True
    assert all_tools.recovery_success is True
    assert all_tools.extra_tool_calls == 1
    assert all_tools.rerouting_events == 0


def test_comparison_reports_recovery_cost_and_success_separately():
    rows = run_comparison(_tool_failure_scenario())
    summary = summarize_recovery_comparison(rows)

    assert summary["conditions"] == 3
    assert summary["final_task_successes"] == 2
    assert summary["recovery_successes"] == 2
    assert summary["rerouting_events"] == 1
    assert summary["extra_model_calls"] == 1
    assert summary["extra_tool_calls"] == 2
    assert summary["latency_overhead_ms"] == 3.0
    assert summary["token_overhead"] == 24

    rerouted = summary["by_condition"]["reroute_on_change"]
    assert rerouted["recovery_success"] is True
    assert rerouted["final_task_success"] is True
    assert rerouted["required_tool_survived_after_change"] is True
