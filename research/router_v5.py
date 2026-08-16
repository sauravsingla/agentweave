from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from research.router_v2 import FAMILIES, RouterPrediction
from research.router_v4 import HierarchicalFamilyRouterV4


# V5 targets browser goals that are transactional or social but may not contain
# explicit UI words such as "page", "button", or "form". These signals are
# benchmark-independent and are frozen before the first successful V5 holdout
# score.
_COMMERCE_RE = re.compile(
    r"\b(buy|purchase|order|checkout|cart|wishlist|product|item|seller|shipping|delivery|"
    r"least expensive|cheapest|most expensive|price|review|rating|category)\b",
    re.I,
)
_SOCIAL_RE = re.compile(
    r"\b(post|comment|reply|upvote|downvote|subreddit|reddit|thread|message|profile|community|"
    r"follow|unfollow|author)\b",
    re.I,
)
_CLASSIFIED_RE = re.compile(
    r"\b(classified|listing|listings|seller|contact|advertisement|ad|condition|pickup|offer)\b",
    re.I,
)
_WEB_ACTION_RE = re.compile(
    r"\b(find|search|filter|sort|select|choose|open|navigate|go to|add|remove|change|update|"
    r"create|delete|buy|purchase|order|post|comment|reply|message|contact)\b",
    re.I,
)
_EXPLICIT_FACT_RE = re.compile(
    r"^\s*(who|what|when|where|why|which|how many|how much)\b",
    re.I,
)


class InteractiveIntentRouterV5(HierarchicalFamilyRouterV4):
    """Router V5 with a browser-goal intent layer over Router V4.

    V5 is intentionally additive. It keeps V4's frozen hierarchy and adds only
    benchmark-independent evidence for transactional/social/classifieds browser
    goals that often omit explicit UI vocabulary.
    """

    def __init__(
        self,
        *,
        commerce_bonus: float = 0.48,
        social_bonus: float = 0.46,
        classifieds_bonus: float = 0.44,
        action_bonus: float = 0.18,
        temperature: float = 0.18,
        **kwargs,
    ):
        super().__init__(temperature=temperature, **kwargs)
        self.commerce_bonus = float(commerce_bonus)
        self.social_bonus = float(social_bonus)
        self.classifieds_bonus = float(classifieds_bonus)
        self.action_bonus = float(action_bonus)

    def fit(self, examples: Iterable[tuple[str, str]]) -> "InteractiveIntentRouterV5":
        super().fit(examples)
        return self

    def _interactive_evidence(self, text: str) -> Counter[str]:
        evidence: Counter[str] = Counter()
        normalized = text.strip()
        commerce = bool(_COMMERCE_RE.search(normalized))
        social = bool(_SOCIAL_RE.search(normalized))
        classifieds = bool(_CLASSIFIED_RE.search(normalized))
        action = bool(_WEB_ACTION_RE.search(normalized))
        explicit_fact = bool(_EXPLICIT_FACT_RE.search(normalized))

        if commerce:
            evidence["terminalbench"] += self.commerce_bonus
        if social:
            evidence["terminalbench"] += self.social_bonus
        if classifieds:
            evidence["terminalbench"] += self.classifieds_bonus

        # Generic actions alone are weak evidence because factual search prompts
        # also contain words such as "find". Pairing them with a web-domain
        # object provides an additional browser-goal signal.
        if action and (commerce or social or classifieds):
            evidence["terminalbench"] += self.action_bonus

        # Avoid turning ordinary fact questions into browser-interaction tasks
        # solely because they mention a product, profile, or post.
        if explicit_fact and not action:
            evidence["search"] += self.action_bonus * 0.65

        return evidence

    def predict(self, text: str) -> RouterPrediction:
        if not self._fitted:
            raise RuntimeError("Router V5 must be fitted before prediction")

        v4 = super().predict(text)
        scores = {family: float(v4.scores[family]) for family in FAMILIES}
        for family, value in self._interactive_evidence(text).items():
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
