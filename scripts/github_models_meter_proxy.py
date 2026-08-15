from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx


class Meter:
    def __init__(self, label: str, log_path: Path):
        self.label = label
        self.log_path = log_path
        self.lock = threading.Lock()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, row: dict[str, Any]) -> None:
        row = {"label": self.label, "ts": time.time(), **row}
        with self.lock:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")


def _json_or_none(data: bytes) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def _usage_and_tools(content: bytes, content_type: str) -> tuple[dict[str, int], int]:
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    tool_keys: set[str] = set()
    parsed = _json_or_none(content)
    payloads: list[Any] = []
    if parsed is not None:
        payloads = [parsed]
    elif "text/event-stream" in content_type or content.startswith(b"data:"):
        for raw in content.decode("utf-8", errors="ignore").splitlines():
            raw = raw.strip()
            if not raw.startswith("data:"):
                continue
            data = raw[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                payloads.append(json.loads(data))
            except Exception:
                pass

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        u = payload.get("usage") or {}
        if isinstance(u, dict):
            for key in usage:
                try:
                    usage[key] = max(usage[key], int(u.get(key) or 0))
                except Exception:
                    pass
        for choice in payload.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message") or choice.get("delta") or {}
            if not isinstance(message, dict):
                continue
            for tc in message.get("tool_calls") or []:
                if isinstance(tc, dict):
                    tool_keys.add(str(tc.get("id") or tc.get("index") or len(tool_keys)))
    return usage, len(tool_keys)


def make_handler(meter: Meter, upstream: str, token: str | None, model_ids: list[str], github_headers: bool):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _normalized_path(self) -> str:
            path = self.path
            if path.startswith("/v1/"):
                path = path[3:]
            if not path.startswith("/"):
                path = "/" + path
            return path

        def do_GET(self) -> None:  # noqa: N802
            path = self._normalized_path()
            if path.rstrip("/") == "/models":
                body = json.dumps({"object": "list", "data": [{"id": m, "object": "model"} for m in model_ids]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                meter.write({"method": "GET", "path": path, "status": 200, "kind": "local-model-list"})
                return
            self._forward(b"")

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0") or 0)
            self._forward(self.rfile.read(length) if length else b"")

        def _forward(self, body: bytes) -> None:
            path = self._normalized_path()
            url = upstream.rstrip("/") + path
            request_json = _json_or_none(body)
            model = request_json.get("model") if isinstance(request_json, dict) else None
            stream = bool(request_json.get("stream")) if isinstance(request_json, dict) else False
            tools_offered = len(request_json.get("tools") or []) if isinstance(request_json, dict) else 0
            headers = {
                "Accept": self.headers.get("Accept", "application/json"),
                "Content-Type": self.headers.get("Content-Type", "application/json"),
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
            if github_headers:
                headers["X-GitHub-Api-Version"] = "2026-03-10"
                headers["Accept"] = "application/vnd.github+json"

            started = time.perf_counter()
            response = None
            error = None
            for attempt in range(1, 4):
                try:
                    with httpx.Client(timeout=900.0) as client:
                        response = client.request(self.command, url, content=body, headers=headers)
                    if response.status_code not in {429, 500, 502, 503, 504} or attempt == 3:
                        break
                    time.sleep(min(12.0, 2.0 ** attempt))
                except Exception as exc:
                    error = repr(exc)
                    if attempt == 3:
                        break
                    time.sleep(min(12.0, 2.0 ** attempt))

            wall_ms = (time.perf_counter() - started) * 1000.0
            if response is None:
                out = json.dumps({"error": {"message": error or "upstream request failed"}}).encode()
                status = 502
                ctype = "application/json"
            else:
                out = response.content
                status = response.status_code
                ctype = response.headers.get("Content-Type", "application/json")

            usage, tool_calls = _usage_and_tools(out, ctype)
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            meter.write({
                "method": self.command,
                "path": path,
                "model": model,
                "stream": stream,
                "status": status,
                "wall_ms": round(wall_ms, 3),
                "request_bytes": len(body),
                "response_bytes": len(out),
                "tools_offered": tools_offered,
                "usage": usage,
                "tool_calls": tool_calls,
                "error_preview": out.decode("utf-8", errors="ignore")[:300] if status >= 400 else None,
            })

    return Handler


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--upstream", default="http://127.0.0.1:11434/v1")
    p.add_argument("--models", default="llama3.2:3b,granite3.3:2b,qwen3-vl:2b")
    p.add_argument("--token-env")
    p.add_argument("--github-headers", action="store_true")
    args = p.parse_args()
    token = os.environ.get(args.token_env) if args.token_env else None
    meter = Meter(args.label, Path(args.log))
    handler = make_handler(
        meter,
        args.upstream,
        token,
        [x.strip() for x in args.models.split(",") if x.strip()],
        args.github_headers,
    )
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    meter.write({"kind": "proxy-start", "port": args.port, "upstream": args.upstream})
    try:
        server.serve_forever()
    finally:
        meter.write({"kind": "proxy-stop"})
        server.server_close()


if __name__ == "__main__":
    main()
