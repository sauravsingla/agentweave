from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "MadeAgents/Hammer2.1-0.5b"


def _strip_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t.get("function", t) for t in tools]


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            calls = []
            for tc in m["tool_calls"]:
                fn = tc.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try: args = json.loads(args)
                    except Exception: args = {}
                calls.append({"name": fn.get("name"), "arguments": args})
            out.append({"role": "assistant", "content": "```\n" + json.dumps(calls, ensure_ascii=False) + "\n```"})
        else:
            item = {"role": role, "content": m.get("content") or ""}
            if role == "tool" and m.get("name"):
                item["name"] = m["name"]
            out.append(item)
    return out


def _extract_calls(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    candidates = [cleaned]
    for match in re.finditer(r"\[[\s\S]*?\]|\{[\s\S]*?\}", cleaned):
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except Exception:
            continue
        if isinstance(obj, dict): obj = [obj]
        if isinstance(obj, list):
            calls = []
            for x in obj:
                if isinstance(x, dict) and x.get("name"):
                    args = x.get("arguments", {})
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except Exception: args = {}
                    calls.append({"name": x["name"], "arguments": args})
            if calls: return calls
    return []


class LocalHammer:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        self.model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.float32)
        self.model.eval()
        self.lock = Lock()

    def complete(self, messages, tools):
        msgs = _normalize_messages(messages)
        tool_specs = _strip_tools(tools)
        with self.lock, torch.inference_mode():
            inputs = self.tokenizer.apply_chat_template(
                msgs, tools=tool_specs, add_generation_prompt=True,
                return_dict=True, return_tensors="pt"
            )
            started = time.perf_counter()
            output = self.model.generate(**inputs, max_new_tokens=128, do_sample=False)
            elapsed = time.perf_counter() - started
            prompt_n = int(inputs["input_ids"].shape[-1])
            gen = output[0][prompt_n:]
            text = self.tokenizer.decode(gen, skip_special_tokens=True)
            calls = _extract_calls(text)
            if calls:
                message = {"role": "assistant", "content": None, "tool_calls": [
                    {"id": f"call_{uuid.uuid4().hex[:12]}", "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["arguments"], separators=(",", ":"))}}
                    for c in calls
                ]}
                finish = "tool_calls"
            else:
                message = {"role": "assistant", "content": text}
                finish = "stop"
            return message, prompt_n, int(gen.shape[-1]), elapsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9100)
    args = ap.parse_args()
    engine = LocalHammer()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): return
        def _send(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            self._send(200, {"object":"list","data":[{"id":MODEL_ID,"object":"model"}]})
        def do_POST(self):
            size = int(self.headers.get("content-length", "0")); payload = json.loads(self.rfile.read(size) or b"{}")
            try:
                msg, inp, out, latency = engine.complete(payload.get("messages") or [], payload.get("tools") or [])
                self._send(200, {"id":f"chatcmpl-{uuid.uuid4().hex[:10]}","object":"chat.completion","model":MODEL_ID,"choices":[{"index":0,"message":msg,"finish_reason":"tool_calls" if msg.get("tool_calls") else "stop"}],"usage":{"prompt_tokens":inp,"completion_tokens":out,"total_tokens":inp+out},"local_inference_seconds":latency})
            except Exception as exc:
                self._send(500, {"error":{"message":repr(exc)}})

    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()

if __name__ == "__main__": main()
