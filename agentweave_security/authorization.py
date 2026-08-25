from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Protocol, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason_code: str
    detail: str = ""


class AuthorizationPolicy(Protocol):
    def authorize(self, *, action: str, context: Mapping[str, object]) -> AuthorizationDecision:
        ...


class AuthorizationDenied(PermissionError):
    def __init__(self, action: str, decision: AuthorizationDecision):
        super().__init__(f"authorization denied for {action}: {decision.reason_code}")
        self.action = action
        self.decision = decision


@dataclass(frozen=True)
class CandidateDrop:
    candidate: str
    reason_code: str


@dataclass(frozen=True)
class StageObservation:
    stage: str
    candidates_in: int
    candidates_out: int
    dropped: tuple[CandidateDrop, ...] = ()
    selected: str | None = None
    authorization_allowed: bool | None = None
    authorization_reason: str | None = None
    latency_ms: float | None = None

    @property
    def narrowed_to_zero(self) -> bool:
        return self.candidates_in > 0 and self.candidates_out == 0


@dataclass
class StageTelemetry:
    observations: list[StageObservation] = field(default_factory=list)

    def record(self, observation: StageObservation) -> None:
        self.observations.append(observation)

    @property
    def zero_candidate_events(self) -> int:
        return sum(obs.narrowed_to_zero for obs in self.observations)

    @property
    def unauthorized_attempts(self) -> int:
        return sum(
            obs.authorization_allowed is False
            for obs in self.observations
        )

    def as_dict(self) -> dict:
        return {
            "zero_candidate_events": self.zero_candidate_events,
            "unauthorized_attempts": self.unauthorized_attempts,
            "stages": [
                {
                    "stage": obs.stage,
                    "candidates_in": obs.candidates_in,
                    "candidates_out": obs.candidates_out,
                    "dropped": [
                        {"candidate": item.candidate, "reason_code": item.reason_code}
                        for item in obs.dropped
                    ],
                    "selected": obs.selected,
                    "authorization_allowed": obs.authorization_allowed,
                    "authorization_reason": obs.authorization_reason,
                    "latency_ms": obs.latency_ms,
                    "narrowed_to_zero": obs.narrowed_to_zero,
                }
                for obs in self.observations
            ],
        }


class AuthorizationGate:
    """Deterministic, fail-closed gate that runs after model selection and before execution.

    The executor callback is invoked only when the policy returns an explicit allow.
    Policy exceptions, missing decisions, malformed results, and explicit denials all
    fail closed.
    """

    def __init__(self, policy: AuthorizationPolicy, telemetry: StageTelemetry | None = None):
        self.policy = policy
        self.telemetry = telemetry or StageTelemetry()

    def authorize(self, *, action: str, context: Mapping[str, object]) -> AuthorizationDecision:
        try:
            decision = self.policy.authorize(action=action, context=context)
        except Exception as exc:
            decision = AuthorizationDecision(False, "policy_error", type(exc).__name__)

        if not isinstance(decision, AuthorizationDecision):
            decision = AuthorizationDecision(False, "invalid_policy_decision")

        self.telemetry.record(
            StageObservation(
                stage="authorization",
                candidates_in=1,
                candidates_out=1 if decision.allowed else 0,
                selected=action,
                authorization_allowed=decision.allowed,
                authorization_reason=decision.reason_code,
            )
        )
        return decision

    def execute(
        self,
        *,
        action: str,
        context: Mapping[str, object],
        executor: Callable[[], T],
    ) -> T:
        decision = self.authorize(action=action, context=context)
        if not decision.allowed:
            raise AuthorizationDenied(action, decision)
        return executor()


def observe_narrowing_stage(
    *,
    telemetry: StageTelemetry,
    stage: str,
    candidates_in: Iterable[str],
    candidates_out: Iterable[str],
    reason_codes: Mapping[str, str] | None = None,
    latency_ms: float | None = None,
) -> StageObservation:
    before = tuple(candidates_in)
    after = tuple(candidates_out)
    after_set = set(after)
    reasons = reason_codes or {}
    dropped = tuple(
        CandidateDrop(candidate=item, reason_code=reasons.get(item, "unspecified"))
        for item in before
        if item not in after_set
    )
    observation = StageObservation(
        stage=stage,
        candidates_in=len(before),
        candidates_out=len(after),
        dropped=dropped,
        latency_ms=latency_ms,
    )
    telemetry.record(observation)
    return observation
