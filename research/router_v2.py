from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Sequence

from agentweave.requirements import RequirementAnalyzer


FAMILIES = (
    "mathhay",
    "mcpbench",
    "search",
    "swebench",
    "tau2bench",
    "terminalbench",
)

# Generic capability descriptions are fixed metadata, not benchmark examples.
FAMILY_SEEDS = {
    "mathhay": "mathematics arithmetic algebra geometry probability calculation numerical reasoning solve equation numbers",
    "mcpbench": "model context protocol mcp tool server function api integration external tools",
    "search": "research search browse web evidence sources retrieval find information factual investigation",
    "swebench": "software engineering code coding bug fix implementation function python repository tests programming",
    "tau2bench": "customer support policy rules account transaction booking allowed compliance service procedure",
    "terminalbench": "shell bash linux terminal command filesystem file directory process package command line unix",
}

_TOKEN_RE = re.compile(r"[a-z0-9_./+:-]+")
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class RouterPrediction:
    family: str
    confidence: float
    scores: dict[str, float]


class PrototypeFamilyRouterV2:
    """A deterministic hybrid prototype router for research evaluation.

    V2 learns TF-IDF family centroids from development examples and combines them
    with the frozen RequirementAnalyzer's benchmark-independent capability signal.
    It uses no external model, no benchmark label at prediction time, and no
    holdout examples during fitting.
    """

    def __init__(self, *, legacy_bonus: float = 0.12, temperature: float = 0.16):
        self.legacy_bonus = float(legacy_bonus)
        self.temperature = float(temperature)
        self.analyzer = RequirementAnalyzer()
        self.idf: dict[str, float] = {}
        self.centroids: dict[str, dict[str, float]] = {}
        self._fitted = False

    @staticmethod
    def _normalized(text: str) -> str:
        return _SPACE_RE.sub(" ", text.lower()).strip()

    @classmethod
    def _features(cls, text: str) -> Counter[str]:
        normalized = cls._normalized(text)
        tokens = _TOKEN_RE.findall(normalized)
        features: Counter[str] = Counter()
        for token in tokens:
            features[f"w:{token}"] += 1
        for left, right in zip(tokens, tokens[1:]):
            features[f"b:{left}_{right}"] += 1

        # Character n-grams make the representation robust to identifiers,
        # command syntax, code fragments, and unseen word forms without adding
        # benchmark-specific hand rules.
        compact = normalized[:2200]
        for i in range(max(0, len(compact) - 3)):
            features[f"c4:{compact[i:i + 4]}"] += 1
        return features

    @staticmethod
    def _l2_normalize(vector: dict[str, float]) -> dict[str, float]:
        norm = math.sqrt(sum(value * value for value in vector.values()))
        if norm <= 0.0:
            return vector
        return {key: value / norm for key, value in vector.items()}

    def fit(self, examples: Iterable[tuple[str, str]]) -> "PrototypeFamilyRouterV2":
        rows = [(str(text), str(family).lower()) for text, family in examples]
        if not rows:
            raise ValueError("Router V2 requires at least one development example")
        unknown = sorted({family for _, family in rows} - set(FAMILIES))
        if unknown:
            raise ValueError(f"Unknown Router V2 family labels: {unknown}")

        # Add one generic seed document per family. This prevents a family from
        # losing all signal if a development fold happens to be small.
        documents: list[tuple[str, str, float]] = [
            (text, family, 1.0) for text, family in rows
        ] + [
            (seed, family, 0.35) for family, seed in FAMILY_SEEDS.items()
        ]

        raw_features: list[tuple[Counter[str], str, float]] = []
        document_frequency: Counter[str] = Counter()
        for text, family, weight in documents:
            feats = self._features(text)
            raw_features.append((feats, family, weight))
            document_frequency.update(feats.keys())

        n_docs = len(raw_features)
        self.idf = {
            feature: math.log((1.0 + n_docs) / (1.0 + df)) + 1.0
            for feature, df in document_frequency.items()
        }

        family_sums: dict[str, defaultdict[str, float]] = {
            family: defaultdict(float) for family in FAMILIES
        }
        family_weights: Counter[str] = Counter()
        for feats, family, weight in raw_features:
            total = float(sum(feats.values())) or 1.0
            for feature, count in feats.items():
                family_sums[family][feature] += weight * (count / total) * self.idf[feature]
            family_weights[family] += weight

        self.centroids = {}
        for family in FAMILIES:
            denom = float(family_weights[family]) or 1.0
            averaged = {feature: value / denom for feature, value in family_sums[family].items()}
            self.centroids[family] = self._l2_normalize(averaged)

        self._fitted = True
        return self

    def _vectorize(self, text: str) -> dict[str, float]:
        feats = self._features(text)
        total = float(sum(feats.values())) or 1.0
        vector = {
            feature: (count / total) * self.idf[feature]
            for feature, count in feats.items()
            if feature in self.idf
        }
        return self._l2_normalize(vector)

    @staticmethod
    def _cosine(vector: dict[str, float], centroid: dict[str, float]) -> float:
        if len(vector) > len(centroid):
            vector, centroid = centroid, vector
        return sum(value * centroid.get(feature, 0.0) for feature, value in vector.items())

    @staticmethod
    def legacy_family(requirement) -> str:
        caps = {str(v).lower() for v in requirement.capabilities}
        domains = {str(v).lower() for v in requirement.domains}
        if caps & {"mcp", "tool-use", "integration"}:
            return "mcpbench"
        if caps & {"operating-system", "shell"}:
            return "terminalbench"
        if "compliance" in caps or "compliance" in domains:
            return "tau2bench"
        if caps & {"coding", "backend", "frontend", "database", "sql"}:
            return "swebench"
        if caps & {"research", "retrieval", "knowledge-graph"}:
            return "search"
        return "mathhay"

    def predict(self, text: str) -> RouterPrediction:
        if not self._fitted:
            raise RuntimeError("Router V2 must be fitted before prediction")
        vector = self._vectorize(text)
        scores = {family: self._cosine(vector, centroid) for family, centroid in self.centroids.items()}

        # Preserve the existing generic requirement analyzer as a weak prior;
        # the learned prototype remains the dominant signal.
        legacy = self.legacy_family(self.analyzer.analyze(text))
        scores[legacy] += self.legacy_bonus

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


def train_router(examples: Sequence[tuple[str, str]]) -> PrototypeFamilyRouterV2:
    return PrototypeFamilyRouterV2().fit(examples)
