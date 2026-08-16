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


def _tool_text(tool: dict[str, Any]) -> str:
    fn = tool.get("function", tool)
    return " ".join(str(x) for x in (fn.get("name", ""), fn.get("description", "")) if x)

def _tool_name(tool: dict[str, Any]) -> str:
    return str(tool.get("function", tool).get("name", "tool"))

def _provider_group(name: str) -> str:
    clean = name.replace(".", "_")
    bits = [b for b in clean.split("_") if b]
    if len(bits) <= 1: return clean
    if clean.startswith("GorillaFileSystem_"): return "GorillaFileSystem"
    if bits[0].lower().endswith("api"): return bits[0]
    return bits[0]

def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            c = message.get("content", "")
            return c if isinstance(c, str) else json.dumps(c, sort_keys=True)
    return json.dumps(messages[-1] if messages else {}, sort_keys=True)

class Router:
    def __init__(self, strategy: str, semantic_top_k: int = 12, max_agents: int = 3, max_tools: int = 24):
        self.strategy, self.semantic_top_k, self.max_agents, self.max_tools = strategy, semantic_top_k, max_agents, max_tools
        self._model = None
    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return self._model
    def _similarities(self, query, texts):
        if not texts: return []
        vectors = self.model.encode([query] + texts, normalize_embeddings=True)
        return [float(vectors[0] @ v) for v in vectors[1:]]
    def select(self, messages, tools):
        if self.strategy == "single-agent" or not tools: return tools
        query = _latest_user_text(messages)
        if self.strategy == "semantic-router":
            scores = self._similarities(query, [_tool_text(t) for t in tools])
            order = sorted(range(len(tools)), key=lambda i: (-scores[i], _tool_name(tools[i])))
            return [tools[i] for i in order[:self.semantic_top_k]]
        if self.strategy != "agentweave": raise ValueError(self.strategy)
        groups = {}
        for tool in tools: groups.setdefault(_provider_group(_tool_name(tool)), []).append(tool)
        names = sorted(groups); scores = self._similarities(query, [" ".join(_tool_text(t) for t in groups[n]) for n in names])
        scored = sorted(zip(names, scores), key=lambda x: (-x[1], x[0])); required = {n for n,_ in scored[:min(self.max_agents,len(scored))]}
        req = Requirement(text=query, capabilities=required, inference_confidence=1.0, inference_source="bfcl-local-preregistered")
        score_map = dict(scored); ranked=[]
        for name in names:
            matched={name} if name in required else set(); norm=max(0.0,min(1.0,(score_map[name]+1)/2))
            agent=AgentProfile(agent_id=f"bfcl:{name}",name=name,capabilities=[Capability(name=name,proficiency=norm,validated=True)],trust=TrustVector(identity=.8,capability=.8,domain=.8,execution=.8,security=.8,collaboration=.8,historical=.8),execution=ExecutionProfile(location="local",latency_ms=1,cost=0))
            ranked.append(MatchResult(agent=agent,score=norm,matched_capabilities=matched,missing_capabilities=required-matched))
        team=GlobalTeamOptimizer().select(req,ranked,max_agents=self.max_agents); selected=[]
        for r in team: selected.extend(groups[r.agent.name])
        if len(selected)>self.max_tools:
            s=self._similarities(query,[_tool_text(t) for t in selected]); order=sorted(range(len(selected)),key=lambda i:(-s[i],_tool_name(selected[i]))); selected=[selected[i] for i in order[:self.max_tools]]
        return selected or tools[:1]

class Metrics:
    def __init__(self,path): self.path=path; self.lock=Lock(); path.parent.mkdir(parents=True,exist_ok=True)
    def write(self,row):
        with self.lock,self.path.open("a",encoding="utf-8") as f: f.write(json.dumps(row,sort_keys=True)+"\n")

def make_handler(router,metrics,upstream_url,upstream_model):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): return
        def _json(self,status,payload):
            body=json.dumps(payload).encode(); self.send_response(status); self.send_header("content-type","application/json"); self.send_header("content-length",str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_GET(self): self._json(200,{"object":"list","data":[{"id":upstream_model,"object":"model"}]})
        def do_POST(self):
            size=int(self.headers.get("content-length","0")); payload=json.loads(self.rfile.read(size) or b"{}")
            original=list(payload.get("tools") or []); selected=router.select(payload.get("messages") or [],original); payload["tools"]=selected; payload["model"]=upstream_model; payload["stream"]=False
            started=time.perf_counter(); error=None; rp={}; status=500
            try:
                response=httpx.post(upstream_url.rstrip("/")+"/chat/completions",json=payload,timeout=300); status=response.status_code; rp=response.json(); error=rp if status>=400 else None
            except Exception as exc: error=repr(exc); rp={"error":str(exc)}
            latency=time.perf_counter()-started; usage=rp.get("usage") or {}
            metrics.write({"strategy":router.strategy,"latency_seconds":latency,"http_status":status,"input_tokens":int(usage.get("prompt_tokens") or 0),"output_tokens":int(usage.get("completion_tokens") or 0),"external_api_spend_usd":0.0,"tools_before":len(original),"tools_after":len(selected),"selected_tools":[_tool_name(t) for t in selected],"error":error})
            self._json(status,rp)
    return Handler

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--strategy",required=True); ap.add_argument("--port",type=int,required=True); ap.add_argument("--metrics",type=Path,required=True); args=ap.parse_args()
    router=Router(args.strategy); metrics=Metrics(args.metrics); url=os.environ.get("LOCAL_MODEL_BASE_URL","http://127.0.0.1:9100/v1"); model=os.environ.get("LOCAL_MODEL_ID","MadeAgents/Hammer2.1-0.5b")
    ThreadingHTTPServer(("127.0.0.1",args.port),make_handler(router,metrics,url,model)).serve_forever()

if __name__=="__main__": main()
