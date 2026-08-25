import pytest

from agentweave_security.authorization import (
    AuthorizationDecision,
    AuthorizationDenied,
    AuthorizationGate,
    StageTelemetry,
    observe_narrowing_stage,
)


class StaticPolicy:
    def __init__(self, allowed: bool, reason: str):
        self.allowed = allowed
        self.reason = reason

    def authorize(self, *, action, context):
        return AuthorizationDecision(self.allowed, self.reason)


class ExplodingPolicy:
    def authorize(self, *, action, context):
        raise RuntimeError("policy unavailable")


def test_unauthorized_model_selected_action_never_executes():
    telemetry = StageTelemetry()
    gate = AuthorizationGate(StaticPolicy(False, "scope_denied"), telemetry)
    executed = []

    with pytest.raises(AuthorizationDenied):
        gate.execute(
            action="delete_account",
            context={"tenant": "t1"},
            executor=lambda: executed.append(True),
        )

    assert executed == []
    assert telemetry.unauthorized_attempts == 1
    assert telemetry.zero_candidate_events == 1
    assert telemetry.observations[-1].authorization_reason == "scope_denied"


def test_authorized_action_executes_once():
    gate = AuthorizationGate(StaticPolicy(True, "explicit_allow"))
    calls = []

    result = gate.execute(
        action="read_profile",
        context={},
        executor=lambda: calls.append("ran") or "ok",
    )

    assert result == "ok"
    assert calls == ["ran"]
    assert gate.telemetry.unauthorized_attempts == 0


def test_policy_error_fails_closed():
    gate = AuthorizationGate(ExplodingPolicy())
    executed = []

    with pytest.raises(AuthorizationDenied) as exc:
        gate.execute(action="transfer", context={}, executor=lambda: executed.append(True))

    assert executed == []
    assert exc.value.decision.reason_code == "policy_error"


def test_malformed_policy_result_fails_closed():
    class BadPolicy:
        def authorize(self, *, action, context):
            return True

    gate = AuthorizationGate(BadPolicy())
    with pytest.raises(AuthorizationDenied) as exc:
        gate.execute(action="tool", context={}, executor=lambda: "should-not-run")

    assert exc.value.decision.reason_code == "invalid_policy_decision"


def test_narrowing_stage_records_counts_reason_codes_and_zero_transition():
    telemetry = StageTelemetry()

    observation = observe_narrowing_stage(
        telemetry=telemetry,
        stage="policy_filter",
        candidates_in=["safe", "malicious"],
        candidates_out=[],
        reason_codes={"safe": "tenant_scope", "malicious": "prompt_injection"},
        latency_ms=1.5,
    )

    assert observation.candidates_in == 2
    assert observation.candidates_out == 0
    assert observation.narrowed_to_zero is True
    assert telemetry.zero_candidate_events == 1
    assert {d.candidate: d.reason_code for d in observation.dropped} == {
        "safe": "tenant_scope",
        "malicious": "prompt_injection",
    }


def test_stage_telemetry_serializes_selected_and_authorization_decision():
    telemetry = StageTelemetry()
    gate = AuthorizationGate(StaticPolicy(False, "role_denied"), telemetry)
    gate.authorize(action="admin_tool", context={"role": "viewer"})

    payload = telemetry.as_dict()
    assert payload["unauthorized_attempts"] == 1
    assert payload["stages"][0]["stage"] == "authorization"
    assert payload["stages"][0]["selected"] == "admin_tool"
    assert payload["stages"][0]["authorization_allowed"] is False
    assert payload["stages"][0]["authorization_reason"] == "role_denied"
