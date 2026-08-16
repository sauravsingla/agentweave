from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from research.router_v2 import FAMILIES, RouterPrediction
from research.router_v5 import InteractiveIntentRouterV5


# V6 broadens interactive recognition from domain nouns (commerce/social/etc.)
# to natural imperative web goals: find-and-act, account/content mutation, and
# multi-constraint navigation. These signals are benchmark-independent and are
# frozen before the first successful V6 holdout score.
_IMPERATIVE_ACTION_RE = re.compile(
    r"^\s*(find|search|locate|open|go to|navigate|visit|create|add|remove|delete|edit|update|change|"
    r"set|submit|send|post|comment|reply|message|order|buy|purchase|cancel|book|reserve|compare|"
    r"filter|sort|select|choose|download|upload|mark|move|copy|share|follow|unfollow)\b",
    re.I,
)
_WEB_OBJECT_RE = re.compile(
    r"\b(account|profile|cart|order|booking|reservation|product|item|listing|post|comment|message|"
    r"thread|issue|repository|repo|project|ticket|page|site|website|dashboard|record|form|address|"
    r"payment|invoice|review|rating|category|user|customer|email|notification|settings|calendar)\b",
    re.I,
)
_CONSTRAINT_RE = re.compile(
    r"\b(before|after|between|under|over|less than|more than|at least|at most|cheapest|lowest|highest|"
    r"most recent|latest|oldest|specific|named|with|without|from|to|in the last|during)\b",
    re.I,
)
_MUTATION_RE = re.compile(
    r"\b(create|add|remove|delete|edit|update|change|set|submit|send|post|comment|reply|message|"
    r"order|buy|purchase|cancel|book|reserve|mark|move|copy|share|follow|unfollow)\b",
    re.I,
)
_CODE_RE = re.compile(r"(^|\n)\s*(def|class|import|from)\s+|```|\bpython\b|\bfunction\b|\bcode\b", re.I)
_MATH_RE = re.compile(r"\b(equation|calculate|compute|probability|algebra|geometry|integral|derivative)\b", re.I)


class WebGoalRouterV6(InteractiveIntentRouterV5):
    """Router V6 with a high-recall natural web-goal layer over Router V5."""

    def __init__(
        self,
        *,
        imperative_bonus: float = 0.34,
        object_bonus: float = 0.26,
        mutation_bonus: float = 0.28,
        constraint_bonus: float = 0.16,
        temperature: float = 0.18,
        **kwargs,
    ):
        super().__init__(temperature=temperature, **kwargs)
        self.imperative_bonus = float(imperative_bonus)
        self.object_bonus = float(object_bonus)
        self.mutation_bonus = float(mutation_bonus)
        self.constraint_bonus = float(constraint_bonus)

    def fit(self, examples: Iterable[tuple[str, str]]) -> "WebGoalRouterV6":
        super().fit(examples)
        return self

    def _web_goal_evidence(self, text: str) -> Counter[str]:
        evidence: Counter[str] = Counter()
        normalized = text.strip()
        if _CODE_RE.search(normalized) or _MATH_RE.search(normalized):
            return evidence

        imperative = bool(_IMPERATIVE_ACTION_RE.search(normalized))
        web_object = bool(_WEB_OBJECT_RE.search(normalized))
        mutation = bool(_MUTATION_RE.search(normalized))
        constrained = bool(_CONSTRAINT_RE.search(normalized))

        if imperative:
            evidence["terminalbench"] += self.imperative_bonus
        if web_object:
            evidence["terminalbench"] += self.object_bonus
        if mutation:
            evidence["terminalbench"] += self.mutation_bonus
        if constrained and (imperative or web_object):
            evidence["terminalbench"] += self.constraint_bonus
        return evidence

    def predict(self, text: str) -> RouterPrediction:
        if not self._fitted:
            raise RuntimeError("Router V6 must be fitted before prediction")

        v5 = super().predict(text)
        scores = {family: float(v5.scores[family]) for family in FAMILIES}
        for family, value in self._web_goal_evidence(text).items():
            scores[family] += value

        best = max(FAMILIES, key=lambda family: (scores[family], family))
        shifted = {family: scores[family] / self.temperature for family in FAMILIES}
        max_score = max(shifted.values())
        exp_scores = {family: math.exp(value - max_score) for family, value in shifted.items()}
        denom = sum(exp_scores.values()) or 1.0
        probabilities = {family: value / denom for family, value in exp_scores.items()}
        return RouterPrediction(
            family=best,
            confidence=probabilities[best],
            scores={family: round(scores[family], 8) for family in FAMILIES},
        )
