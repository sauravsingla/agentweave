from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Mapping, Any

from .models import Requirement

SemanticInferencer = Callable[[str], Mapping[str, Any] | None]


@dataclass(frozen=True)
class _Concept:
    capabilities: frozenset[str]
    domains: frozenset[str] = frozenset()
    knowledge: frozenset[str] = frozenset()
    terms: tuple[str, ...] = ()
    phrases: tuple[str, ...] = ()
    min_score: float = 1.0


class RequirementAnalyzer:
    """Layered requirement inference with explicit uncertainty.

    Layer 1 is deterministic lexical/phrase matching. Layer 2 adds generic semantic
    intent heuristics for task classes whose domain is often implicit in natural
    language. Layer 3 is an optional pluggable semantic/LLM inferencer that can enrich
    low-confidence requests.

    The built-in layers do not consume benchmark labels or expected specialist IDs.
    """

    ontology = {
        "research": {"research", "evidence", "literature", "investigate"},
        "summarization": {"summarize", "summary", "brief"},
        "analysis": {"analyze", "analyse", "evaluate", "assess"},
        "coding": {"code", "program", "python", "c++", "software", "javascript", "typescript"},
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
        _Concept(
            capabilities=frozenset({"frontend", "web-ui", "coding"}),
            domains=frozenset({"frontend", "web-ui"}),
            knowledge=frozenset({"browser-ui"}),
            terms=(
                "html", "css", "dom", "svg", "react", "vue", "svelte", "angular",
                "frontend", "browser", "viewport", "responsive", "canvas", "webgl",
                "button", "sidebar", "modal", "layout", "stylesheet", "animation",
            ),
            phrases=(
                "user interface", "web page", "web app", "landing page", "responsive layout",
                "browser ui", "front end", "visual layout", "dom element", "css grid",
            ),
            min_score=1.5,
        ),
        _Concept(
            capabilities=frozenset({"backend", "api", "coding"}),
            domains=frozenset({"backend"}),
            knowledge=frozenset({"services"}),
            terms=(
                "backend", "server", "service", "services", "endpoint", "endpoints", "api",
                "fastapi", "django", "flask", "express", "webhook", "authentication", "oauth",
                "jwt", "queue", "worker", "redis", "mongodb", "persistence", "concurrency",
            ),
            phrases=(
                "rest api", "http api", "api endpoint", "backend service", "web service",
                "server side", "authentication flow", "background worker", "message queue",
            ),
            min_score=1.5,
        ),
        _Concept(
            capabilities=frozenset({"game-development", "coding"}),
            domains=frozenset({"game-development"}),
            knowledge=frozenset({"interactive-systems"}),
            terms=(
                "game", "gameplay", "player", "collision", "score", "winner", "board",
                "level", "physics", "sprite", "move", "moves", "replay",
            ),
            phrases=(
                "win detection", "game loop", "player controls", "board game", "game state",
            ),
            min_score=1.5,
        ),
        _Concept(
            capabilities=frozenset({"mcp", "tool-use", "integration"}),
            domains=frozenset({"mcp"}),
            knowledge=frozenset({"tool-protocols"}),
            terms=("mcp",),
            phrases=("model context protocol", "mcp server", "mcp tool"),
            min_score=1.0,
        ),
    )

    factual_question_starters = ("who ", "where ", "when ", "which ", "what ")
    factual_relation_terms = {
        "born", "birth", "died", "death", "spouse", "married", "parent", "parents",
        "child", "children", "sibling", "founded", "founder", "created", "author",
        "written", "wrote", "directed", "director", "produced", "producer", "capital",
        "country", "city", "state", "nationality", "occupation", "profession", "member",
        "team", "university", "school", "company", "organization", "language", "genre",
        "religion", "located", "location", "headquartered", "owned", "owner", "award",
        "played", "plays", "works", "worked", "influenced", "influence", "part", "belongs",
    }
    technical_blockers = {
        "sql", "database", "table", "schema", "query", "column", "row", "bash", "shell",
        "terminal", "linux", "unix", "filesystem", "chmod", "grep", "systemctl", "python",
        "code", "program", "html", "css", "javascript", "typescript", "api", "server",
        "frontend", "backend",
    }

    def __init__(self, semantic_inferencer: SemanticInferencer | None = None):
        self.semantic_inferencer = semantic_inferencer

    @staticmethod
    def _normalize(text: str) -> tuple[str, set[str], list[str]]:
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        ordered = re.findall(r"[a-z0-9+._/-]+", normalized)
        return normalized, set(ordered), ordered

    @staticmethod
    def _concept_score(concept: _Concept, normalized: str, tokens: set[str]) -> float:
        term_hits = sum(1.0 for term in concept.terms if term in tokens)
        phrase_hits = sum(2.0 for phrase in concept.phrases if phrase in normalized)
        return term_hits + phrase_hits

    def _semantic_intent(self, normalized: str, tokens: set[str], ordered: list[str], inferred_domains: set[str]):
        if inferred_domains:
            return None
        starts_as_question = normalized.startswith(self.factual_question_starters)
        relation_hits = tokens & self.factual_relation_terms
        blocked = bool(tokens & self.technical_blockers)
        concise = 2 <= len(ordered) <= 40
        possessive_relation = bool(re.search(r"\b[a-z0-9._-]+'s\s+[a-z]", normalized))
        if starts_as_question and concise and not blocked and (relation_hits or possessive_relation or "?" in normalized):
            return {
                "capabilities": {"knowledge-graph", "retrieval", "reasoning"},
                "domains": {"knowledge-graph"},
                "knowledge": {"graph-data"},
                "confidence": 0.68 if relation_hits or possessive_relation else 0.62,
                "source": "semantic-factual-retrieval",
            }
        return None

    @staticmethod
    def _merge_external(result: Mapping[str, Any] | None):
        if not result:
            return None
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
        return {
            "capabilities": {str(v).lower() for v in result.get("capabilities", [])},
            "domains": {str(v).lower() for v in result.get("domains", [])},
            "knowledge": {str(v).lower() for v in result.get("knowledge", [])},
            "confidence": confidence,
            "source": str(result.get("source") or "external-semantic-inferencer"),
        }

    def analyze(
        self,
        text: str,
        domains=None,
        knowledge=None,
        local_only: bool = False,
        max_latency_ms=None,
        privacy_level=None,
    ):
        normalized, tokens, ordered = self._normalize(text)
        caps = {capability for capability, vocabulary in self.ontology.items() if tokens & vocabulary}
        inferred_domains: set[str] = set()
        inferred_knowledge: set[str] = set()
        confidence = 0.45 if caps else 0.0
        sources: list[str] = []
        ambiguity: list[str] = []

        concept_matches: list[tuple[float, _Concept]] = []
        for concept in self.concepts:
            score = self._concept_score(concept, normalized, tokens)
            if score >= concept.min_score:
                concept_matches.append((score, concept))

        if concept_matches:
            best = max(score for score, _ in concept_matches)
            selected = [(score, concept) for score, concept in concept_matches if score >= max(concept.min_score, best - 1.0)]
            if len(selected) > 1:
                ambiguity.append("multiple-specialist-signals")
            for score, concept in selected:
                caps.update(concept.capabilities)
                inferred_domains.update(concept.domains)
                inferred_knowledge.update(concept.knowledge)
                confidence = max(confidence, min(0.96, 0.72 + 0.06 * score))
            sources.append("lexical-specialist")

        semantic = self._semantic_intent(normalized, tokens, ordered, inferred_domains)
        if semantic:
            caps.update(semantic["capabilities"])
            inferred_domains.update(semantic["domains"])
            inferred_knowledge.update(semantic["knowledge"])
            confidence = max(confidence, semantic["confidence"])
            sources.append(semantic["source"])

        if self.semantic_inferencer and confidence < 0.75:
            external = self._merge_external(self.semantic_inferencer(text))
            if external and external["confidence"] > confidence:
                caps.update(external["capabilities"])
                inferred_domains.update(external["domains"])
                inferred_knowledge.update(external["knowledge"])
                confidence = external["confidence"]
                sources.append(external["source"])

        if not caps:
            caps = {"reasoning"}
            confidence = max(confidence, 0.25)
            sources.append("reasoning-fallback")

        explicit_domains = {str(v).lower() for v in (domains or [])}
        explicit_knowledge = {str(v).lower() for v in (knowledge or [])}
        if explicit_domains or explicit_knowledge:
            inferred_domains.update(explicit_domains)
            inferred_knowledge.update(explicit_knowledge)
            confidence = max(confidence, 0.99)
            sources.append("explicit-constraints")

        local_only = local_only or any(marker in normalized for marker in ("local only", "on-device", "on device", "offline", "do not send outside"))

        return Requirement(
            text=text,
            capabilities={str(v).lower() for v in caps},
            domains=inferred_domains,
            knowledge=inferred_knowledge,
            local_only=local_only,
            max_latency_ms=max_latency_ms,
            privacy_level=privacy_level,
            inference_confidence=confidence,
            inference_source="+".join(dict.fromkeys(sources)) if sources else None,
            ambiguity=ambiguity,
        )
