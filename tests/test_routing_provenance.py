from agentweave_security.authorization import AuthorizationDecision, AuthorizationGate, StageTelemetry
from agentweave_security.routing_provenance import (
    ExecutionRecord,
    ModelCallRecord,
    build_tool_routing_provenance,
)
from agentweave_security.scope_filter import (
    ScopeContext,
    ScopedTool,
    StaticScopeFilter,
    apply_policy_then_optional_routing,
)


class _AllowLookup:
    def authorize(self, *, action, context):
        return AuthorizationDecision(action == "lookup", "allowed" if action == "lookup" else "denied")


def _fixture():
    tools = (
        ScopedTool("lookup", roles=frozenset({"analyst"})),
        ScopedTool("verify", roles=frozenset({"analyst"})),
        ScopedTool("admin_export", roles=frozenset({"admin"})),
    )
    context = ScopeContext(role="analyst")
    result = apply_policy_then_optional_routing(
        tools=tools,
        context=context,
        scope_filter=StaticScopeFilter(policy_version="policy-v7"),
        router=lambda rows: tuple(tool for tool in rows if tool.name == "lookup"),
        router_version="router-v3",
    )
    return tools, result


def test_provenance_distinguishes_policy_and_router_drops():
    tools, result = _fixture()
    record = build_tool_routing_provenance(
        source_tools=tools,
        routing_result=result,
        model_call=ModelCallRecord(selected_action="lookup", arguments={"q": "x"}),
        execution=ExecutionRecord(True, True, "allowed", True, True, "ok"),
    )

    assert record.source_catalog == ("lookup", "verify", "admin_export")
    assert record.policy_filtered_out == ("admin_export",)
    assert record.policy_filter_reasons["admin_export"] == "role_not_allowed"
    assert record.policy_permitted == ("lookup", "verify")
    assert record.router_filtered_out == ("verify",)
    assert record.model_visible_tools == ("lookup",)
    assert record.router_version == "router-v3"


def test_provenance_captures_model_authorization_execution_and_telemetry():
    tools, result = _fixture()
    telemetry = StageTelemetry()
    gate = AuthorizationGate(_AllowLookup(), telemetry)
    decision = gate.authorize(action="lookup", context={})

    record = build_tool_routing_provenance(
        source_tools=tools,
        routing_result=result,
        model_call=ModelCallRecord(selected_action="lookup", call_id="call-1"),
        execution=ExecutionRecord(
            attempted=True,
            authorized=decision.allowed,
            authorization_reason=decision.reason_code,
            executed=True,
            success=True,
            result_code="ok",
            recovery_attempted=True,
            recovery_success=True,
        ),
        telemetry=telemetry,
    )

    assert record.model_call.selected_action == "lookup"
    assert record.execution.authorized is True
    assert record.execution.recovery_success is True
    assert record.stage_telemetry["stages"][0]["stage"] == "authorization"
    assert "lookup" in record.to_json()
    assert len(record.record_hash) == 64


def test_serialization_is_deterministic():
    tools, result = _fixture()
    kwargs = dict(
        source_tools=tools,
        routing_result=result,
        model_call=ModelCallRecord(selected_action="lookup", arguments={"b": 2, "a": 1}),
        execution=ExecutionRecord(True, True, "allowed", True, True),
    )
    first = build_tool_routing_provenance(**kwargs)
    second = build_tool_routing_provenance(**kwargs)
    assert first.to_json() == second.to_json()
    assert first.record_hash == second.record_hash
