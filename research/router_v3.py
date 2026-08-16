from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from research.router_v2 import FAMILIES, PrototypeFamilyRouterV2, RouterPrediction


# Benchmark-independent task-intent anchors. These are fixed before the first
# Router V3 holdout score and intentionally describe broad capabilities rather
# than benchmark names or task instances.
SEMANTIC_ANCHORS = {
    "mathhay": (
        "solve calculate compute mathematics arithmetic algebra geometry probability "
        "number equation percentage count numeric reasoning"
    ),
    "mcpbench": (
        "use external tool api function service integration protocol server connector "
        "invoke tool call endpoint"
    ),
    "search": (
        "answer factual question research find information verify fact evidence source "
        "knowledge lookup investigate who what when where why which"
    ),
    "swebench": (
        "write implement create debug fix code program function method algorithm python "
        "software return input output list string integer tests"
    ),
    "tau2bench": (
        "customer support policy account booking refund transaction service procedure "
        "rules eligibility compliance allowed"
    ),
    "terminalbench": (
        "operate computer desktop operating system application window settings browser "
        "file folder shell terminal command linux click open close move rename install"
    ),
}

_CODE_RE = re.compile(
    r"\b(write|implement|create|define|debug|fix)\b.{0,45}\b(function|method|program|code|algorithm|class)\b"
    r"|\b(function|method|program|code|algorithm|class)\b.{0,45}\b(return|input|output|list|string|integer|array)\b",
    re.I | re.S,
)
_QUESTION_RE = re.compile(r"^\s*(who|what|when|where|why|which|how)\b", re.I)
_OS_RE = re.compile(
    r"\b(desktop|application|window|browser|settings|folder|file manager|menu|toolbar|tab|open|close|click|rename|move|copy)\b",
    re.I,
)
_TOOL_RE = re.compile(r"\b(api|tool|endpoint|server|connector|integration|invoke|function call|mcp)\b", re.I)
_POLICY_RE = re.compile(r"\b(policy|refund|booking|customer|account|transaction|eligib|compliance|allowed)\b", re.I)
_MATH_RE = re.compile(r"\b(calculate|compute|sum|product|equation|percent|probability|integer|number)\b", re.I)


class SemanticFamilyRouterV3(PrototypeFamilyRouterV2):
    """Deterministic Router V3 for cross-distribution family transfer.

    V3 retains V2's development-trained TF-IDF prototype centroids, but adds a
    second benchmark-independent semantic-anchor representation plus small
    structural intent bonuses. It uses no external model and no holdout label
    at prediction time.
    """

    def __init__(
        self,
        *,
        legacy_bonus: float = 0.08,
        anchor_weight: float = 0.34,
        structural_bonus: float = 0.22,
        temperature: float = 0.17,
    ):
        super().__init__(legacy_bonus=legacy_bonus, temperature=temperature)
        self.anchor_weight = float(anchor_weight)
        self.structural_bonus = float(structural_bonus)
        self.anchor_vectors: dict[str, dict[str, float]] = {}

    def fit(self, examples: Iterable[tuple[str, str]]) -> "SemanticFamilyRouterV3":
        rows = list(examples)
        super().fit(rows)
        self.anchor_vectors = {
            family: self._vectorize(text) for family, text in SEMANTIC_ANCHORS.items()
        }
        return self

    def _intent_bonuses(self, text: str) -> Counter[str]:
        bonus: Counter[str] = Counter()
        normalized = text.strip()
        if _CODE_RE.search(normalized):
            bonus["swebench"] += self.structural_bonus
        if _QUESTION_RE.search(normalized) and not _CODE_RE.search(normalized):
            bonus["search"] += self.structural_bonus * 0.72
        if _OS_RE.search(normalized) and not _CODE_RE.search(normalized):
            bonus["terminalbench"] += self.structural_bonus * 0.72
        if _TOOL_RE.search(normalized):
            bonus["mcpbench"] += self.structural_bonus * 0.55
        if _POLICY_RE.search(normalized):
            bonus["tau2bench"] += self.structural_bonus * 0.65
        if _MATH_RE.search(normalized) and not _CODE_RE.search(normalized):
            bonus["mathhay"] += self.structural_bonus * 0.45
        return bonus

    def predict(self, text: str) -> RouterPrediction:
        if not self._fitted:
            raise RuntimeError("Router V3 must be fitted before prediction")

        vector = self._vectorize(text)
        scores = {
            family: self._cosine(vector, centroid)
            for family, centroid in self.centroids.items()
        }

        for family in FAMILIES:
            scores[family] += self.anchor_weight * self._cosine(
                vector, self.anchor_vectors[family]
            )

        legacy = self.legacy_family(self.analyzer.analyze(text))
        scores[legacy] += self.legacy_bonus
        for family, value in self._intent_bonuses(text).items():
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
