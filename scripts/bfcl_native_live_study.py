from __future__ import annotations

import argparse, hashlib, json, math, os, random, statistics, subprocess, sys, time
from pathlib import Path

# BFCL compatibility transport only. This registry entry uses BFCL's
# OpenAICompletionsHandler so the benchmark sends the actual multi-turn
# `messages` and `tools` to our local routing proxy. The proxy always
# overwrites the model with LOCAL_MODEL_ID; MiniCPM-SALA is never executed.
BFCL_HANDLER_MODEL_ID = "openbmb/MiniCPM-SALA-FC"
LOCAL_MODEL_ID = "MadeAgents/Hammer2.1-0.5b"
CATEGORY = "multi_turn_base"
SAMPLE_SEED = "agentweave-bfcl-native-v1:"
STRATEGIES = ("single-agent", "semantic-router", "agentweave")

def load_jsonl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
def select_ids(data_file,n=12):
    rows=load_jsonl(data_file); ranked=sorted((hashlib.sha256((SAMPLE_SEED+r["id"]).encode()).hexdigest(),r["id"]) for r in rows)
    return sorted(i for _,i in ranked[:n])
def wilson(s,n,z=1.959963984540054):
    if not n:return (0.,0.)
    p=s/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d;return max(0.,c-h),min(1.,c+h)
def exact_mcnemar(a,b):
    n10=sum(x and not y for x,y in zip(a,b));n01=sum((not x) and y for x,y in zip(a,b));n=n10+n01
    if n==0:return 1.0
    k=min(n10,n01);return min(1.0,2*sum(math.comb(n,i) for i in range(k+1))/(2**n))
def paired_bootstrap(a,b,seed=20260816,reps=10000):
    if not a:return (0.,0.)
    rng=random.Random(seed);n=len(a);v=[]
    for _ in range(reps):
        idx=[rng.randrange(n) for _ in range(n)];v.append(sum(a[i]-b[i] for i in idx)/n)
    v.sort();return v[int(.025*(reps-1))],v[int(.975*(reps-1))]
def read_score_rows(score_dir,sampled_ids):
    files=sorted(dict.fromkeys(list(Path(score_dir).rglob("*multi_turn_base*score*.json"))+list(Path(score_dir).rglob("*multi_turn_base*.json"))))
    rows=[]
    for f in files:
        try:c=load_jsonl(f)
        except Exception:continue
        if c and any("valid" in r for r in c):rows=c;break
    if not rows:raise RuntimeError("No BFCL per-task valid records")
    out={str(r["id"]):bool(r.get("valid")) for r in rows if r.get("id") is not None}
    if not out and len(rows)==len(sampled_ids):out={i:bool(r.get("valid")) for i,r in zip(sampled_ids,rows)}
    missing=set(sampled_ids)-set(out)
    if missing:raise RuntimeError(f"Missing sampled ids: {sorted(missing)}")
    return {i:out[i] for i in sampled_ids}
def summarize_metrics(path):
    rows=load_jsonl(path) if Path(path).exists() else []
    return {"model_calls":len(rows),"mean_call_latency_seconds":statistics.fmean(r["latency_seconds"] for r in rows) if rows else 0.,"median_call_latency_seconds":statistics.median(r["latency_seconds"] for r in rows) if rows else 0.,"input_tokens":sum(int(r.get("input_tokens",0)) for r in rows),"output_tokens":sum(int(r.get("output_tokens",0)) for r in rows),"external_api_spend_usd":0.0,"mean_tools_before":statistics.fmean(r["tools_before"] for r in rows) if rows else 0.,"mean_tools_after":statistics.fmean(r["tools_after"] for r in rows) if rows else 0.,"errors":[r for r in rows if r.get("error")]}
def wait_http(url,timeout=300):
    import httpx
    deadline=time.time()+timeout
    while time.time()<deadline:
        try:
            if httpx.get(url,timeout=2).status_code==200:return
        except Exception:pass
        time.sleep(1)
    raise RuntimeError(f"Service not ready: {url}")
def run_strategy(strategy,bfcl_root,output_root,sampled_ids,port):
    run_root=output_root/strategy;run_root.mkdir(parents=True,exist_ok=True);(run_root/"test_case_ids_to_generate.json").write_text(json.dumps({CATEGORY:sampled_ids},indent=2))
    metrics=run_root/"provider_metrics.jsonl";env=os.environ.copy();env["BFCL_PROJECT_ROOT"]=str(run_root.resolve());env["OPENAI_API_KEY"]="local-no-key-shim";env["OPENAI_BASE_URL"]=f"http://127.0.0.1:{port}/v1";env["LOCAL_MODEL_BASE_URL"]="http://127.0.0.1:9100/v1";env["LOCAL_MODEL_ID"]=LOCAL_MODEL_ID
    proxy=subprocess.Popen([sys.executable,str((Path(__file__).parent/"bfcl_routing_proxy.py").resolve()),"--strategy",strategy,"--port",str(port),"--metrics",str(metrics.resolve())],env=env)
    try:
        wait_http(f"http://127.0.0.1:{port}/v1/models",30)
        subprocess.run(["bfcl","generate","--model",BFCL_HANDLER_MODEL_ID,"--run-ids","--num-threads","1","--include-input-log"],cwd=bfcl_root,env=env,check=True)
        subprocess.run(["bfcl","evaluate","--model",BFCL_HANDLER_MODEL_ID,"--test-category",CATEGORY,"--partial-eval"],cwd=bfcl_root,env=env,check=True)
    finally:
        proxy.terminate()
        try:proxy.wait(timeout=10)
        except subprocess.TimeoutExpired:proxy.kill()
    return read_score_rows(run_root/"score",sampled_ids),summarize_metrics(metrics)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--bfcl-root",type=Path,required=True);ap.add_argument("--output",type=Path,default=Path("bfcl-native-live-results"));ap.add_argument("--protocol",type=Path,default=Path("evaluation/bfcl-native-live-v1.json"));ap.add_argument("--validate-only",action="store_true");args=ap.parse_args()
    protocol=json.loads(args.protocol.read_text());assert protocol["benchmark"]["commit"]=="6ea57973c7a6097fd7c5915698c54c17c5b1b6c8";assert protocol["benchmark"]["sample_size"]==12;assert protocol["inference"]["model"]==LOCAL_MODEL_ID;assert protocol["status"]=="preregistered-before-first-score"
    data=args.bfcl_root/"bfcl_eval"/"data"/"BFCL_v4_multi_turn_base.json";ids=select_ids(data,12);args.output.mkdir(parents=True,exist_ok=True);(args.output/"sampled_ids.json").write_text(json.dumps(ids,indent=2))
    if args.validate_only:
        print(json.dumps({"protocol_valid":True,"sample_count":len(ids),"sample_sha256":hashlib.sha256("\n".join(ids).encode()).hexdigest(),"local_model":LOCAL_MODEL_ID,"bfcl_transport_model":BFCL_HANDLER_MODEL_ID},indent=2));return
    model_server=subprocess.Popen([sys.executable,str((Path(__file__).parent/"bfcl_local_hammer_server.py").resolve()),"--port","9100"])
    try:
        wait_http("http://127.0.0.1:9100/v1/models",600)
        score_maps={};metrics={}
        for idx,strategy in enumerate(STRATEGIES):score_maps[strategy],metrics[strategy]=run_strategy(strategy,args.bfcl_root,args.output,ids,8760+idx)
    finally:
        model_server.terminate()
        try:model_server.wait(timeout=10)
        except subprocess.TimeoutExpired:model_server.kill()
    results={}
    for s in STRATEGIES:
        flags=[score_maps[s][i] for i in ids];succ=sum(flags);results[s]={"successes":succ,"n":len(flags),"native_task_success":succ/len(flags),"wilson_95_ci":list(wilson(succ,len(flags))),**metrics[s]}
    comparisons={}
    for b in ("single-agent","semantic-router"):
        a=[float(score_maps["agentweave"][i]) for i in ids];bb=[float(score_maps[b][i]) for i in ids];comparisons[b]={"agentweave_minus_baseline_pp":100*(statistics.fmean(a)-statistics.fmean(bb)),"paired_bootstrap_95_ci_pp":[100*x for x in paired_bootstrap(a,bb)],"exact_mcnemar_p":exact_mcnemar([bool(x) for x in a],[bool(x) for x in bb])}
    failures=[{"id":i,"strategy":s} for i in ids for s in STRATEGIES if not score_maps[s][i]]
    payload={"study_id":protocol["study_id"],"benchmark_commit":protocol["benchmark"]["commit"],"model":LOCAL_MODEL_ID,"bfcl_transport_model":BFCL_HANDLER_MODEL_ID,"sampled_ids":ids,"results":results,"comparisons":comparisons,"failure_index":failures,"evidence_boundary":protocol["evidence_boundary"]}
    (args.output/"summary.json").write_text(json.dumps(payload,indent=2,sort_keys=True));print(json.dumps(payload,indent=2,sort_keys=True))
if __name__=="__main__":main()
