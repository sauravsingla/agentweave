from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Requirement


@dataclass(frozen=True)
class _Concept:
    capabilities: frozenset[str]
    domains: frozenset[str] = frozenset()
    knowledge: frozenset[str] = frozenset()
    terms: tuple[str, ...] = ()
    phrases: tuple[str, ...] = ()
    min_score: float = 1.0


class RequirementAnalyzer:
    """Lightweight, deterministic requirement inference.

    The analyzer deliberately uses a generic capability/domain ontology rather than
    benchmark labels. It supports multi-label inference from raw task text and keeps
    a conservative reasoning fallback when no specialist evidence is present.
    """

    ontology = {
        "research": {"research", "evidence", "literature", "investigate"},
        "summarization": {"summarize", "summary", "brief"},
        "analysis": {"analyze", "analyse", "evaluate", "assess"},
        "coding": {"code", "program", "python", "c++", "software"},
        "vision": {"image", "video", "vision", "camera"},
        "forecasting": {"forecast", "predict", "prediction"},
        "optimization": {"optimize", "optimise", "schedule", "routing"},
        "compliance": {"compliance", "regulation", "policy", "legal"},
        "reasoning": {"reason", "decision", "recommend", "plan", "solve"},
    }

    concepts = (
        _Concept(
            capabilities=frozenset({"database", "sql", "reasoning"}),
            domains=frozenset({"database"}),
            knowledge=frozenset({"tabular-data"}),
            terms=(
                "sql", "database", "table", "tables", "schema", "schemas", "query",
                "queries", "join", "joins", "column", "columns", "row", "rows",
                "postgres", "postgresql", "mysql", "sqlite", "transaction",
            ),
            phrases=(
                "select from", "group by", "order by", "primary key", "foreign key",
                "relational database", "database table", "sql query",
            ),
            min_score=1.0,
        ),
        _Concept(
            capabilities=frozenset({"knowledge-graph", "retrieval", "reasoning"}),
            domains=frozenset({"knowledge-graph"}),
            knowledge=frozenset({"graph-data"}),
            terms=(
                "sparql", "rdf", "triples", "triple", "wikidata", "dbpedia",
                "freebase", "ontology", "ontologies", "entity", "entities",
                "relation", "relations", "predicate", "predicates",
            ),
            phrases=(
                "knowledge graph", "entity relation", "entity relationship",
                "subject predicate object", "graph query", "rdf graph",
                "which entity", "relationship between",
            ),
            min_score=1.5,
        ),
        _Concept(
            capabilities=frozenset({"operating-system", "shell", "reasoning"}),
            domains=frozenset({"operating-system"}),
            knowledge=frozenset({"linux"}),
            terms=(
                "bash", "shell", "terminal", "linux", "unix", "filesystem",
                "directory", "directories", "chmod", "chown", "grep", "awk", "sed",
                "process", "processes", "pid", "sudo", "apt", "systemctl", "cron",
            ),
            phrases=(
                "command line", "file permission", "file permissions", "shell command",
                "linux command", "terminal command", "operating system", "package manager",
                "working directory", "environment variable",
            ),
            min_score=1.0,
        ),
    )

    @staticmethod
    def _normalize(text: str) -> tuple[str, set[str]]:
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        tokens = set(re.findall(r"[a-z0-9+._/-]+", normalized))
        return normalized, tokens

    @staticmethod
    def _concept_score(concept: _Concept, normalized: str, tokens: set[str]) -> float:
        term_hits = sum(1.0 for term in concept.terms if term in tokens)
        phrase_hits = sum(2.0 for phrase in concept.phrases if phrase in normalized)
        return term_hits + phrase_hits

    def analyze(
        self,
        text: str,
        domains=None,
        knowledge=None,
        local_only: bool = False,
        max_latency_ms=None,
        privacy_level=None,
    ):
        normalized, tokens = self._normalize(text)

        caps = {
            capability
            for capability, vocabulary in self.ontology.items()
            if tokens & vocabulary
        }
        inferred_domains: set[str] = set()
        inferred_knowledge: set[str] = set()

        concept_matches: list[tuple[float, _Concept]] = []
        for concept in self.concepts:
            score = self._concept_score(concept, normalized, tokens)
            if score >= concept.min_score:
                concept_matches.append((score, concept))

        # Keep all strong specialist signals. For ambiguous single-token evidence,
        # retain only the strongest concept rather than spraying unrelated domains.
        if concept_matches:
            best = max(score for score, _ in concept_matches)
            selected = [
                concept
                for score, concept in concept_matches
                if score >= max(concept.min_score, best - 1.0)
            ]
            for concept in selected:
                caps.update(concept.capabilities)
                inferred_domains.update(concept.domains)
                inferred_knowledge.update(concept.knowledge)

        # Reasoning is a useful generic capability, but it should not erase specialist
        # evidence. It remains the fallback only when no capability evidence exists.
        if not caps:
            caps = {"reasoning"}

        explicit_domains = {str(v).lower() for v in (domains or [])}
        explicit_knowledge = {str(v).lower() for v in (knowledge or [])}
        inferred_domains.update(explicit_domains)
        inferred_knowledge.update(explicit_knowledge)

        local_only = local_only or any(
            marker in normalized
            for marker in ("local only", "on-device", "on device", "offline", "do not send outside")
        )

        return Requirement(
            text=text,
            capabilities={str(v).lower() for v in caps},
            domains=inferred_domains,
            knowledge=inferred_knowledge,
            local_only=local_only,
            max_latency_ms=max_latency_ms,
            privacy_level=privacy_level,
        )
