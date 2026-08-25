from agentweave_security.scope_benchmark import (
    ScopeBenchmarkCondition,
    run_scope_benchmark,
    run_scope_benchmark_comparison,
)


def test_all_conditions_preserve_required_tool_success():
    outcomes = run_scope_benchmark_comparison()
    assert len(outcomes) == 3
    assert all(outcome.task_success for outcome in outcomes)


def test_policy_only_removes_denied_tools_before_model_visibility():
    all_tools = run_scope_benchmark(ScopeBenchmarkCondition.ALL_TOOLS)
    policy_only = run_scope_benchmark(ScopeBenchmarkCondition.POLICY_ONLY)

    assert policy_only.model_visible_candidates < all_tools.model_visible_candidates
    assert policy_only.policy_denied_visible == 0
    assert policy_only.input_token_proxy < all_tools.input_token_proxy


def test_policy_plus_routing_reduces_catalog_further():
    policy_only = run_scope_benchmark(ScopeBenchmarkCondition.POLICY_ONLY)
    routed = run_scope_benchmark(ScopeBenchmarkCondition.POLICY_PLUS_ROUTING)

    assert routed.model_visible_candidates < policy_only.model_visible_candidates
    assert routed.model_visible_candidates == 1
    assert routed.relevant_visible == 1
    assert routed.policy_denied_visible == 0
    assert routed.input_token_proxy < policy_only.input_token_proxy
    assert routed.routing_latency_ms > 0


def test_modeled_latency_keeps_stage_costs_explicit():
    all_tools = run_scope_benchmark(ScopeBenchmarkCondition.ALL_TOOLS)
    policy_only = run_scope_benchmark(ScopeBenchmarkCondition.POLICY_ONLY)
    routed = run_scope_benchmark(ScopeBenchmarkCondition.POLICY_PLUS_ROUTING)

    assert all_tools.policy_latency_ms == 0
    assert policy_only.policy_latency_ms > 0
    assert routed.policy_latency_ms > 0
    assert routed.routing_latency_ms > 0
