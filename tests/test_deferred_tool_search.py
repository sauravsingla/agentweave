from agentweave_security.deferred_tool_search import (
    DisclosureCondition,
    ScenarioKind,
    default_scenarios,
    run_deferred_benchmark,
    run_deferred_comparison,
    summarize_deferred_comparison,
)


def _scenario(kind: ScenarioKind):
    return next(item for item in default_scenarios() if item.kind is kind)


def test_routing_miss_is_recovered_only_with_deferred_search():
    scenario = _scenario(ScenarioKind.ROUTING_MISS)
    routed = run_deferred_benchmark(scenario, DisclosureCondition.POLICY_ROUTING)
    deferred = run_deferred_benchmark(scenario, DisclosureCondition.POLICY_ROUTING_DEFERRED)

    assert routed.task_success is False
    assert deferred.task_success is True
    assert deferred.recovery_success is True
    assert deferred.deferred_search_invocations == 1
    assert deferred.extra_model_round_trips == 1
    assert deferred.extra_tool_calls == 1


def test_state_change_recovers_new_capability_with_search():
    scenario = _scenario(ScenarioKind.STATE_CHANGE)
    routed = run_deferred_benchmark(scenario, DisclosureCondition.POLICY_ROUTING)
    deferred = run_deferred_benchmark(scenario, DisclosureCondition.POLICY_ROUTING_DEFERRED)

    assert routed.task_success is False
    assert deferred.task_success is True
    assert deferred.recovery_success is True
    assert deferred.final_model_visible > deferred.initial_model_visible


def test_unnecessary_search_is_counted_and_adds_overhead():
    scenario = _scenario(ScenarioKind.UNNECESSARY_SEARCH)
    routed = run_deferred_benchmark(scenario, DisclosureCondition.POLICY_ROUTING)
    deferred = run_deferred_benchmark(scenario, DisclosureCondition.POLICY_ROUTING_DEFERRED)

    assert routed.task_success is True
    assert deferred.task_success is True
    assert deferred.unnecessary_searches == 1
    assert deferred.input_token_proxy > routed.input_token_proxy
    assert deferred.total_latency_ms > routed.total_latency_ms


def test_policy_denied_hidden_tool_cannot_be_disclosed_or_executed():
    scenario = _scenario(ScenarioKind.UNAUTHORIZED_HIDDEN)
    deferred = run_deferred_benchmark(scenario, DisclosureCondition.POLICY_ROUTING_DEFERRED)

    assert deferred.task_success is False
    assert deferred.unauthorized_discovery_attempts == 1
    assert deferred.unauthorized_executions == 0
    assert deferred.final_model_visible == deferred.initial_model_visible


def test_policy_only_preserves_required_tool_when_policy_is_sufficient():
    scenario = _scenario(ScenarioKind.POLICY_SUFFICIENT)
    policy = run_deferred_benchmark(scenario, DisclosureCondition.POLICY_ONLY)

    assert policy.task_success is True
    assert policy.initial_model_visible < policy.catalog_total
    assert policy.deferred_search_invocations == 0


def test_large_noisy_catalog_shows_initial_context_reduction():
    scenario = _scenario(ScenarioKind.LARGE_NOISY)
    all_tools = run_deferred_benchmark(scenario, DisclosureCondition.ALL_TOOLS)
    routed = run_deferred_benchmark(scenario, DisclosureCondition.POLICY_ROUTING)

    assert all_tools.catalog_total >= 50
    assert routed.initial_model_visible < all_tools.initial_model_visible
    assert routed.candidate_reduction_pct > 90.0
    assert routed.input_token_proxy < all_tools.input_token_proxy


def test_four_conditions_are_reported_for_every_scenario():
    rows = run_deferred_comparison()
    assert len(rows) == len(default_scenarios()) * len(DisclosureCondition)
    summary = summarize_deferred_comparison(rows)
    assert summary["runs"] == len(rows)
    assert summary["unauthorized_executions"] == 0
