from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .requirements import RequirementAnalyzer

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._/-]*")


def tool_name(tool: Mapping[str, Any]) -> str:
    fn = tool.get("function") if isinstance(tool.get("function"), Mapping) else tool
    return str(fn.get("name") or "tool")


def tool_text(tool: Mapping[str, Any]) -> str:
    fn = tool.get("function") if isinstance(tool.get("function"), Mapping) else tool
    schema = fn.get("parameters", fn.get("inputSchema", {}))
    return " ".join(
        part
        for part in (
            str(fn.get("name") or ""),
            str(fn.get("description") or ""),
            json.dumps(schema, sort_keys=True, default=str),
        )
        if part
    )


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


@dataclass(frozen=True)
class ToolRoutingResult:
    selected: list[Mapping[str, Any]]
    filtered: list[Mapping[str, Any]]
    provenance: dict[str, Any]


class ToolRouter:
    """Small provider-neutral pre-inference router for arbitrary tool catalogs.

    It deliberately has no model dependency. Tools are ranked with deterministic
    lexical/capability signals, while the original tool descriptor objects are
    returned unchanged for the downstream model client.
    """

    version = "agentweave-tool-router-v1"

    def __init__(self, analyzer: RequirementAnalyzer | None = None):
        self.analyzer = analyzer or RequirementAnalyzer()

    def route(
        self,
        text: str,
        tools: Sequence[Mapping[str, Any]],
        *,
        max_tools: int = 8,
    ) -> ToolRoutingResult:
        if max_tools < 1:
            raise ValueError("max_tools must be at least 1")
        catalog = list(tools)
        req = self.analyzer.analyze(text)
        query_tokens = _tokens(text)
        capability_tokens = {c.lower() for c in req.capabilities}

        scored: list[tuple[float, str, int, Mapping[str, Any]]] = []
        for index, tool in enumerate(catalog):
            name = tool_name(tool)
            text_tokens = _tokens(tool_text(tool))
            lexical = len(query_tokens & text_tokens)
            capability = sum(2.0 for cap in capability_tokens if cap in text_tokens or cap in tool_text(tool).lower())
            exact_name = 2.0 if name.lower() in text.lower() else 0.0
            score = float(lexical) + capability + exact_name
            scored.append((score, name.lower(), index, tool))

        # Deterministic ordering is important for replay. If signals are tied or
        # absent, stable tool name and original catalog position break the tie.
        ranked = sorted(scored, key=lambda row: (-row[0], row[1], row[2]))
        selected_rows = ranked[: min(max_tools, len(ranked))]
        selected_indices = {row[2] for row in selected_rows}
        selected = [row[3] for row in selected_rows]
        filtered = [tool for index, tool in enumerate(catalog) if index not in selected_indices]

        catalog_fingerprint = hashlib.sha256(
            json.dumps(catalog, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        provenance = {
            "router": self.version,
            "catalog_sha256": catalog_fingerprint,
            "catalog_size": len(catalog),
            "max_tools": max_tools,
            "required_capabilities": sorted(req.capabilities),
            "selected_tools": [tool_name(t) for t in selected],
            "filtered_tools": [tool_name(t) for t in filtered],
            "scores": [
                {"tool": row[1], "score": row[0]}
                for row in ranked
            ],
        }
        return ToolRoutingResult(selected=selected, filtered=filtered, provenance=provenance)
