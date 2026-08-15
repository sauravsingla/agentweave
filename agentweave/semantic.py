from __future__ import annotations
import math, re, statistics
from dataclasses import dataclass
from typing import Awaitable, Callable

CitationChecker = Callable[[str], Awaitable[float] | float]
Verifier = Callable[[str, list[dict]], Awaitable[dict] | dict]
NLIScorer = Callable[[str, str], Awaitable[float] | float]
SourceQuality = Callable[[str], Awaitable[float] | float]

@dataclass
class SemanticVerdict:
    score: float
    factuality: float
    citation_quality: float
    consistency: float
    uncertainty: float
    contradictions: list[str]
    verifier: dict | None = None
    nli_consistency: float | None = None
    source_quality: float | None = None


class SemanticResultVerifier:
    """Pluggable factuality/citation/NLI verifier with calibrated uncertainty hooks."""
    def __init__(self, citation_checker: CitationChecker | None = None, verifier_agent: Verifier | None = None, nli_scorer: NLIScorer | None = None, source_quality_checker: SourceQuality | None = None):
        self.citation_checker = citation_checker
        self.verifier_agent = verifier_agent
        self.nli_scorer = nli_scorer
        self.source_quality_checker = source_quality_checker

    def _text(self, result):
        value = result.get('response', result) if isinstance(result, dict) else result
        if isinstance(value, dict):
            for key in ('result', 'answer', 'text', 'content', 'decision'):
                if isinstance(value.get(key), str):
                    return value[key]
            return str(value)
        return str(value or '')

    def _tokens(self, text):
        return set(re.findall(r'[a-z0-9]+', text.lower()))

    def _heuristic_consistency(self, texts):
        if len(texts) < 2:
            return 1.0, []
        values, contradictions = [], []
        neg = (' not ', ' no ', ' never ', 'false', 'incorrect', 'reject', 'contradict')
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                left, right = self._tokens(texts[i]), self._tokens(texts[j])
                sim = len(left & right) / max(1, len(left | right))
                values.append(sim)
                left_neg = any(x in ' ' + texts[i].lower() + ' ' for x in neg)
                right_neg = any(x in ' ' + texts[j].lower() + ' ' for x in neg)
                if sim > .35 and left_neg != right_neg:
                    contradictions.append(f'{i}:{j}')
        return sum(values) / max(1, len(values)), contradictions

    def _uncertainty(self, text):
        hits = sum(text.lower().count(x) for x in ('maybe', 'possibly', 'uncertain', 'approximately', 'likely', 'i think', 'cannot verify'))
        explicit = re.findall(r'\b(?:confidence|probability)\s*[:=]?\s*(0(?:\.\d+)?|1(?:\.0+)?|\d{1,3}%)', text.lower())
        if explicit:
            value = explicit[0]
            confidence = float(value[:-1]) / 100 if value.endswith('%') else float(value)
            return max(0.0, min(1.0, 1 - confidence))
        return min(1.0, hits / 5)

    async def _citation_score(self, text):
        urls = re.findall(r'https?://[^\s\]\)]+', text)
        markers = re.findall(r'\[[0-9]+\]|doi:|source:', text, re.I)
        base = min(1.0, .35 * len(urls) + .2 * len(markers))
        source_score = None
        if self.source_quality_checker and urls:
            values = []
            for url in urls:
                value = self.source_quality_checker(url)
                value = await value if hasattr(value, '__await__') else value
                values.append(float(value))
            source_score = statistics.mean(values) if values else 0.0
            base = .55 * base + .45 * source_score
        if self.citation_checker:
            checked = self.citation_checker(text)
            checked = await checked if hasattr(checked, '__await__') else checked
            base = .4 * base + .6 * float(checked)
        return base, source_score

    async def _nli(self, texts):
        if not self.nli_scorer or len(texts) < 2:
            return None, []
        scores, contradictions = [], []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                value = self.nli_scorer(texts[i], texts[j])
                value = await value if hasattr(value, '__await__') else value
                score = max(-1.0, min(1.0, float(value)))
                scores.append(score)
                if score < -.35:
                    contradictions.append(f'nli:{i}:{j}')
        normalized = statistics.mean((x + 1) / 2 for x in scores) if scores else 1.0
        return normalized, contradictions

    async def verify(self, results: list[dict], question: str = '') -> dict:
        texts = [self._text(r) for r in results if r.get('success', True)]
        consistency, contradictions = self._heuristic_consistency(texts)
        nli_consistency, nli_contradictions = await self._nli(texts)
        contradictions.extend(nli_contradictions)
        if nli_consistency is not None:
            consistency = .45 * consistency + .55 * nli_consistency

        citation_scores, source_scores = [], []
        for text in texts:
            citation, source = await self._citation_score(text)
            citation_scores.append(citation)
            if source is not None:
                source_scores.append(source)
        citation_quality = statistics.mean(citation_scores) if citation_scores else 0.0
        source_quality = statistics.mean(source_scores) if source_scores else None
        uncertainty = statistics.mean(self._uncertainty(t) for t in texts) if texts else 1.0

        factuality = max(0.0, min(1.0, .50 * consistency + .28 * citation_quality + .22 * (1 - uncertainty)))
        verifier = None
        if self.verifier_agent:
            value = self.verifier_agent(question, results)
            verifier = await value if hasattr(value, '__await__') else value
            if isinstance(verifier, dict) and 'score' in verifier:
                factuality = .45 * factuality + .55 * float(verifier['score'])

        score = max(0.0, min(1.0, .55 * factuality + .20 * citation_quality + .20 * consistency + .05 * (1 - uncertainty)))
        return SemanticVerdict(score, factuality, citation_quality, consistency, uncertainty, contradictions, verifier, nli_consistency, source_quality).__dict__


class VerificationBenchmark:
    """Measures factual-verifier discrimination and confidence calibration."""
    def brier_score(self, labeled_predictions):
        rows = list(labeled_predictions)
        if not rows:
            return 0.0
        return statistics.mean((float(prob) - int(bool(label))) ** 2 for prob, label in rows)

    def expected_calibration_error(self, labeled_predictions, bins=10):
        rows = [(max(0.0, min(1.0, float(p))), int(bool(y))) for p, y in labeled_predictions]
        if not rows:
            return 0.0
        total = len(rows); ece = 0.0
        for index in range(bins):
            low, high = index / bins, (index + 1) / bins
            bucket = [(p, y) for p, y in rows if low <= p < high or (index == bins - 1 and p == 1.0)]
            if not bucket:
                continue
            confidence = statistics.mean(p for p, _ in bucket)
            accuracy = statistics.mean(y for _, y in bucket)
            ece += len(bucket) / total * abs(confidence - accuracy)
        return ece

    def classification_metrics(self, labeled_scores, threshold=.5):
        tp = fp = tn = fn = 0
        for score, label in labeled_scores:
            pred = float(score) >= threshold; truth = bool(label)
            tp += int(pred and truth); fp += int(pred and not truth); tn += int(not pred and not truth); fn += int(not pred and truth)
        precision = tp / max(1, tp + fp); recall = tp / max(1, tp + fn)
        f1 = 2 * precision * recall / max(1e-12, precision + recall)
        accuracy = (tp + tn) / max(1, tp + fp + tn + fn)
        return {'accuracy': accuracy, 'precision': precision, 'recall': recall, 'f1': f1, 'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn}
