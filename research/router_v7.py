from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from research.router_v2 import FAMILIES, RouterPrediction
from research.router_v6 import WebGoalRouterV6


# V7 distinguishes information-seeking web research from interactive browser
# manipulation. Signals are benchmark-independent and are frozen before the
# first successful V7 holdout score.
_QUESTION_RE = re.compile(
    r"^\s*(who|what|when|where|why|which|how|is|are|was|were|do|does|did|can|could|would|should)\b",
    re.I,
)
_RESEARCH_RE = re.compile(
    r"\b(find out|identify|determine|compare|list|name|research|look up|information|details|according to|"
    r"how many|how much|what are|which are|where can|when did|who is|who was|latest|current|recent|near|"
    r"distance|price|prices|schedule|hours|opening|rating|ratings|review|reviews|statistics|percentage|"
    r"date|dates|year|years|source|sources)\b",
    re.I,
)
_ANSWER_SHAPE_RE = re.compile(
    r"\b(answer|return|provide|give me|tell me|report|include|with the|in a table|as a list|number only|names? only)\b",
    re.I,
)
_MUTATION_RE = re.compile(
    r"\b(create|add|remove|delete|edit|update|change|set|submit|send|post|comment|reply|message|"
    r"order|buy|purchase|cancel|book|reserve|mark|move|copy|share|follow|unfollow|upload)\b",
    re.I,
)
_CODE_RE = re.compile(r"(^|\n)\s*(def|class|import|from)\s+|```|\bpython\b|\bfunction\b|\bcode\b", re.I)
_MATH_RE = re.compile(r"\b(equation|integral|derivative|algebra|geometry|prove|theorem)\b", re.I)


class ResearchIntentRouterV7(WebGoalRouterV6):
    """Router V7 with an information-seeking research gate over Router V6."""

    def __init__(
        self,
        *,
        question_bonus: float = 0.52,
        research_bonus: float = 0.48,
        answer_shape_bonus: float = 0.24,
        mutation_penalty: float = 0.36,
        temperature: float = 0.18,
        **kwargs,
    ):
        super().__init__(temperature=temperature, **kwargs)
        self.question_bonus = float(question_bonus)
        self.research_bonus = float(research_bonus)
        self.answer_shape_bonus = float(answer_shape_bonus)
        self.mutation_penalty = float(mutation_penalty)

    def fit(self, examples: Iterable[tuple[str, str]]) -> "ResearchIntentRouterV7":
        super().fit(examples)
        return self

    def _research_evidence(self, text: str) -> Counter[str]:
        evidence: Counter[str] = Counter()
        normalized = text.strip()
        if _CODE_RE.search(normalized) or _MATH_RE.search(normalized):
            return evidence

        question = bool(_QUESTION_RE.search(normalized)) or normalized.endswith("?")
        research = bool(_RESEARCH_RE.search(normalized))
        answer_shape = bool(_ANSWER_SHAPE_RE.search(normalized))
        mutation = bool(_MUTATION_RE.search(normalized))

        if question:
            evidence["search"] += self.question_bonus
        if research:
            evidence["search"] += self.research_bonus
        if answer_shape and (question or research):
            evidence["search"] += self.answer_shape_bonus

        # Mutating a web state is stronger interaction evidence. This penalty
        # prevents ordinary action tasks from being reclassified as research
        # merely because they contain a question-like phrase.
        if mutation:
            evidence["search"] -= self.mutation_penalty
        return evidence

    def predict(self, text: str) -> RouterPrediction:
        if not self._fitted:
            raise RuntimeError("Router V7 must be fitted before prediction")

        v6 = super().predict(text)
        scores = {family: float(v6.scores[family]) for family in FAMILIES}
        for family, value in self._research_evidence(text).items():
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
