from __future__ import annotations

import json
from typing import Any

from agentweave.models import (
    AgentProfile,
    Capability,
    ExecutionProfile,
    MatchResult,
    Requirement,
    TrustVector,
)
from agentweave.optimizer import GlobalTeamOptimizer


def _tool_name(tool: dict[str, Any]) -> str:
    fn = tool.get("function", tool)
    return str(fn.get("name", "tool"))


def _tool_text(tool: dict[str, Any]) -> str:
    fn = tool.get("function", tool)
    return " ".join(
        str(value)
        for value in (fn.get("name", ""), fn.get("description", ""))
        if value
    )


def _provider_group(name: str) -> str:
    clean = name.replace(".", "_")
    bits = [bit for bit in clean.split("_") if bit]
    if len(bits) <= 1:
        return clean
    if clean.startswith("GorillaFileSystem_"):
        return "GorillaFileSystem"
    if bits[0].lower().endswith("api"):
        return bits[0]
    return bits[0]


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            if isinstance(content, str):
                return content
            return json.dumps(content, sort_keys=True)
    return json.dumps(messages[-1] if messages else {}, sort_keys=True)


class BFCLToolRouter:
    """AgentWeave routing adapter for standard BFCL function lists.

    The router does not modify BFCL questions, evaluator ground truth, or function
    definitions. It only chooses which BFCL-provided candidate functions are
    exposed to the downstream model for a given inference step.
    """

    def __init__(
        self,
        max_provider_agents: int = 4,
        max_tools: int = 6,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        if max_provider_agents < 1:
            raise ValueError("max_provider_agents must be >= 1")
        if max_tools < 1:
            raise ValueError("max_tools must be >= 1")
        self.max_provider_agents = max_provider_agents
        self.max_tools = max_tools
        self.embedding_model = embedding_model
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.embedding_model)
        return self._model

    def _similarities(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        vectors = self.model.encode([query] + texts, normalize_embeddings=True)
        return [float(vectors[0] @ vector) for vector in vectors[1:]]

    def select(
        self,
        messages: list[dict[str, Any]],
        functions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return an AgentWeave-selected subset of the BFCL candidate functions."""
        if len(functions) <= self.max_tools:
            return list(functions)

        query = _latest_user_text(messages)
        groups: dict[str, list[dict[str, Any]]] = {}
        for function in functions:
            groups.setdefault(_provider_group(_tool_name(function)), []).append(function)

        provider_names = sorted(groups)
        provider_scores = self._similarities(
            query,
            [" ".join(_tool_text(tool) for tool in groups[name]) for name in provider_names],
        )
        scored_providers = sorted(
            zip(provider_names, provider_scores), key=lambda item: (-item[1], item[0])
        )
        required = {
            name
            for name, _ in scored_providers[: min(self.max_provider_agents, len(scored_providers))]
        }

        requirement = Requirement(
            text=query,
            capabilities=required,
            inference_confidence=1.0,
            inference_source="bfcl-official-handler",
        )
        score_map = dict(scored_providers)
        ranked: list[MatchResult] = []
        for name in provider_names:
            matched = {name} if name in required else set()
            normalized = max(0.0, min(1.0, (score_map[name] + 1.0) / 2.0))
            agent = AgentProfile(
                agent_id=f"bfcl:{name}",
                name=name,
                capabilities=[Capability(name=name, proficiency=normalized, validated=True)],
                trust=TrustVector(
                    identity=0.8,
                    capability=0.8,
                    domain=0.8,
                    execution=0.8,
                    security=0.8,
                    collaboration=0.8,
                    historical=0.8,
                ),
                execution=ExecutionProfile(location="local", latency_ms=1, cost=0),
            )
            ranked.append(
                MatchResult(
                    agent=agent,
                    score=normalized,
                    matched_capabilities=matched,
                    missing_capabilities=required - matched,
                )
            )

        team = GlobalTeamOptimizer().select(
            requirement,
            ranked,
            max_agents=self.max_provider_agents,
        )

        selected: list[dict[str, Any]] = []
        for result in team:
            selected.extend(groups[result.agent.name])

        if len(selected) > self.max_tools:
            scores = self._similarities(query, [_tool_text(tool) for tool in selected])
            order = sorted(
                range(len(selected)),
                key=lambda idx: (-scores[idx], _tool_name(selected[idx])),
            )
            selected = [selected[idx] for idx in order[: self.max_tools]]

        return selected or [functions[0]]


__all__ = ["BFCLToolRouter"]
