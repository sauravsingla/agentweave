from __future__ import annotations

import argparse
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

from agentweave.models import AgentProfile, Capability, ExecutionProfile, MatchResult, Requirement, TrustVector
from agentweave.optimizer import GlobalTeamOptimizer


PRICE_INPUT = 0.40 / 1_000_000
PRICE_CACHED = 0.10 / 1_000_000
PRICE_OUTPUT = 1.60 / 1_000_000


def _tool_text(tool: dict[str, Any]) -> str:
    fn = tool.get("function", tool)
    return " ".join(str(x) for x in (fn.get("name", ""), fn.get("description", "")) if x)


def _tool_name(tool: dict[str, Any]) -> str:
    fn = tool.get("function", tool)
    return str(fn.get("name", "tool"))


def _provider_group(name: str) -> str:
    clean = name.replace(".", "_")
    bits = [b for b in clean.split("_") if b]
    if len(bits) <= 1:
        return clean
    # BFCL class/provider names such as GorillaFileSystem and TwitterAPI are
    # the stable agent boundary; suffixes are individual functions.
    if bits[0].lower().startswith("gorilla"):
        return bits[0]
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


class Router:
    def __init__(self, strategy: str, semantic_top_k: int = 12, max_agents: int = 3, max_tools: int = 24):
        self.strategy = strategy
        self.semantic_top_k = semantic_top_k
        self.max_agents = max_agents
        self.max_tools = max_tools
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return self._model

    def _similarities(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        vectors = self.model.encode([query] + texts, normalize_embeddings=True)
        q = vectors[0]
        return [float(q @ v) for v in vectors[1:]]

    def select(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.strategy == "single-agent" or not tools:
            return tools
        query = _latest_user_text(messages)
        if self.strategy == "semantic-router":
            scores = self._similarities(query, [_tool_text(t) for t in tools])
            order = sorted(range(len(tools)), key=lambda i: (-scores[i], _tool_name(tools[i])))
            return [tools[i] for i in order[: self.semantic_top_k]]
        if self.strategy != "agentweave":
            raise ValueError(f"Unknown strategy: {self.strategy}")

        groups: dict[str, list[dict[str, Any]]] = {}
        for tool in tools:
            groups.setdefault(_provider_group(_tool_name(tool)), []).append(tool)
        group_names = sorted(groups)
        group_texts = [" ".join(_tool_text(t) for t in groups[name]) for name in group_names]
        scores = self._similarities(query, group_texts)
        scored = sorted(zip(group_names, scores), key=lambda x: (-x[1], x[0]))
        required_groups = {name for name, _ in scored[: min(self.max_agents, len(scored))]}
        req = Requirement(text=query, capabilities=required_groups, inference_confidence=1.0, inference_source="bfcl-live-preregistered")
        ranked: list[MatchResult] = []
        score_map = dict(scored)
        for name in group_names:
            matched = {name} if name in required_groups else set()
            normalized = max(0.0, min(1.0, (score_map[name] + 1.0) / 2.0))
            agent = AgentProfile(
                agent_id=f"bfcl:{name}",
                name=name,
                capabilities=[Capability(name=name, proficiency=normalized, validated=True)],
                trust=TrustVector(identity=.8, capability=.8, domain=.8, execution=.8, security=.8, collaboration=.8, historical=.8),
                execution=ExecutionProfile(location="provider", latency_ms=1.0, cost=0.0),
            )
            ranked.append(MatchResult(agent=agent, score=normalized, matched_capabilities=matched, missing_capabilities=required_groups - matched))
        team = GlobalTeamOptimizer().select(req, ranked, max_agents=self.max_agents)
        selected_groups = [r.agent.name for r in team]
        selected: list[dict[str, Any]] = []
        for group in selected_groups:
            selected.extend(groups[group])
        if len(selected) > self.max_tools:
            local_scores = self._similarities(query, [_tool_text(t) for t in selected])
            order = sorted(range(len(selected)), key=lambda i: (-local_scores[i], _tool_name(selected[i])))
            selected = [selected[i] for i in order[: self.max_tools]]
        if not selected:
            local_scores = self._similarities(query, [_tool_text(t) for t in tools])
            best = max(range(len(tools)), key=lambda i: local_scores[i])
            selected = [tools[best]]
        return selected


class Metrics:
    def __init__(self, path: Path):
        self.path = path
        self.lock = Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, row: dict[str, Any]) -> None:
        with self.lock, self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def make_handler(router: Router, metrics: Metrics, upstream_key: str, upstream_url: str, upstream_model: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path.rstrip("/").endswith("models"):
                self._json(200, {"object": "list", "data": [{"id": upstream_model, "object": "model"}]})
            else:
                self._json(200, {"status": "ok"})

        def do_POST(self) -> None:
            if not self.path.endswith("/chat/completions"):
                self._json(404, {"error": "only chat/completions is proxied"})
                return
            size = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(size) or b"{}")
            original_tools = list(payload.get("tools") or [])
            selected_tools = router.select(payload.get("messages") or [], original_tools)
            payload["tools"] = selected_tools
            payload["model"] = upstream_model
            payload["stream"] = False
            started = time.perf_counter()
            error = None
            response_payload: dict[str, Any] = {}
            status = 500
            try:
                with httpx.Client(timeout=180.0) as client:
                    response = client.post(
                        upstream_url.rstrip("/") + "/chat/completions",
                        headers={"authorization": f"Bearer {upstream_key}", "content-type": "application/json"},
                        json=payload,
                    )
                status = response.status_code
                response_payload = response.json()
                if status >= 400:
                    error = response_payload
            except Exception as exc:
                error = repr(exc)
                response_payload = {"error": str(exc)}
            latency = time.perf_counter() - started
            usage = response_payload.get("usage") or {}
            details = usage.get("prompt_tokens_details") or {}
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            cached_tokens = int(details.get("cached_tokens") or 0)
            uncached_tokens = max(0, prompt_tokens - cached_tokens)
            completion_tokens = int(usage.get("completion_tokens") or 0)
            cost = uncached_tokens * PRICE_INPUT + cached_tokens * PRICE_CACHED + completion_tokens * PRICE_OUTPUT
            metrics.write({
                "strategy": router.strategy,
                "timestamp": time.time(),
                "latency_seconds": latency,
                "http_status": status,
                "input_tokens": prompt_tokens,
                "cached_input_tokens": cached_tokens,
                "output_tokens": completion_tokens,
                "usage_priced_cost_usd": cost,
                "tools_before": len(original_tools),
                "tools_after": len(selected_tools),
                "selected_tools": [_tool_name(t) for t in selected_tools],
                "error": error,
            })
            self._json(status, response_payload)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=["single-agent", "semantic-router", "agentweave"], required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get("UPSTREAM_OPENAI_API_KEY")
    if not key:
        raise SystemExit("UPSTREAM_OPENAI_API_KEY is required for a live provider run")
    router = Router(args.strategy)
    metrics = Metrics(args.metrics)
    handler = make_handler(router, metrics, key, "https://api.openai.com/v1", "gpt-4.1-mini-2025-04-14")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
