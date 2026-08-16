from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from research.router_v2 import FAMILIES, RouterPrediction
from research.router_v3 import SemanticFamilyRouterV3


# V4 adds a hierarchy over broad task modes before family scoring. The signals
# are benchmark-independent and were fixed before the first successful V4
# holdout score.
_CODE_SYNTAX_RE = re.compile(
    r"(^|\n)\s*(def|class|import|from)\s+|\b(return|yield|lambda|assert|print)\b|"
    r"```|\bpython\b|\bprogram\b|\bcode\b|\bfunction\b|\bmethod\b",
    re.I,
)
_CODE_IO_RE = re.compile(r"\b(input|output|returns?|arguments?|parameter|list|dict|tuple|array|string|integer)\b", re.I)
_UI_RE = re.compile(
    r"\b(browser|web page|page|form|field|button|menu|tab|window|desktop|dashboard|record|list view|"
    r"application|app|settings|click|select|choose|navigate|open|close|submit|filter|sort|search box|"
    r"service catalog|incident|request|ticket)\b",
    re.I,
)
_ACTION_RE = re.compile(r"\b(create|update|edit|delete|add|remove|change|set|find|locate|view|go to|mark|order)\b", re.I)
_FACT_RE = re.compile(r"^\s*(who|what|when|where|why|which|how many|how much|name|identify)\b", re.I)
_TOOL_RE = re.compile(r"\b(api|endpoint|tool call|connector|integration|mcp|server function|invoke)\b", re.I)
_POLICY_RE = re.compile(r"\b(policy|refund|eligibility|eligible|account|customer|booking|transaction|compliance|allowed)\b", re.I)
_MATH_RE = re.compile(r"\b(calculate|compute|equation|probability|percentage|percent|sum|product|arithmetic|geometry|algebra)\b", re.I)


class HierarchicalFamilyRouterV4(SemanticFamilyRouterV3):
    """Deterministic hierarchical family router for cross-distribution transfer.

    V4 preserves V3's learned prototypes, semantic anchors, and legacy prior,
    then adds a benchmark-independent task-mode layer. The hierarchy is meant to
    separate interactive UI/browser work from software/code work before final
    family selection, addressing a failure mode visible in V3 without using any
    V3 holdout examples as V4 scoring data.
    """

    def __init__(
        self,
        *,
        legacy_bonus: float = 0.07,
        anchor_weight: float = 0.30,
        structural_bonus: float = 0.31,
        hierarchy_bonus: float = 0.42,
        temperature: float = 0.18,
    ):
        super().__init__(
            legacy_bonus=legacy_bonus,
            anchor_weight=anchor_weight,
            structural_bonus=structural_bonus,
            temperature=temperature,
        )
        self.hierarchy_bonus = float(hierarchy_bonus)

    def fit(self, examples: Iterable[tuple[str, str]]) -> "HierarchicalFamilyRouterV4":
        super().fit(examples)
        return self

    def _mode_evidence(self, text: str) -> Counter[str]:
        evidence: Counter[str] = Counter()
        normalized = text.strip()

        code_syntax = bool(_CODE_SYNTAX_RE.search(normalized))
        code_io = bool(_CODE_IO_RE.search(normalized))
        ui = bool(_UI_RE.search(normalized))
        action = bool(_ACTION_RE.search(normalized))

        # Code syntax plus explicit I/O is strong software evidence. A raw word
        # such as "create" is deliberately not enough to call something code.
        if code_syntax:
            evidence["swebench"] += self.hierarchy_bonus * (1.0 if code_io else 0.78)

        # Interactive UI/browser evidence is strongest when an action is also
        # present. This helps distinguish "create a record in a form" from
        # "create a Python function".
        if ui and not code_syntax:
            evidence["terminalbench"] += self.hierarchy_bonus * (1.0 if action else 0.82)
        elif ui and action and code_syntax:
            evidence["terminalbench"] += self.hierarchy_bonus * 0.18

        if _FACT_RE.search(normalized) and not code_syntax and not (ui and action):
            evidence["search"] += self.hierarchy_bonus * 0.72
        if _TOOL_RE.search(normalized):
            evidence["mcpbench"] += self.hierarchy_bonus * 0.62
        if _POLICY_RE.search(normalized) and not code_syntax:
            evidence["tau2bench"] += self.hierarchy_bonus * 0.60
        if _MATH_RE.search(normalized) and not code_syntax:
            evidence["mathhay"] += self.hierarchy_bonus * 0.52
        return evidence

    def predict(self, text: str) -> RouterPrediction:
        if not self._fitted:
            raise RuntimeError("Router V4 must be fitted before prediction")

        # Start from V3 scores so V4 is an additive research layer rather than a
        # replacement trained on the new holdout.
        v3 = super().predict(text)
        scores = {family: float(v3.scores[family]) for family in FAMILIES}
        for family, value in self._mode_evidence(text).items():
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
