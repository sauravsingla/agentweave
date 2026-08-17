from __future__ import annotations

import argparse, hashlib, json, math, os, random, statistics, subprocess, sys, time
from pathlib import Path

BFCL_HANDLER_MODEL_ID = "openbmb/MiniCPM-SALA-FC"
LOCAL_MODEL_ID = "MadeAgents/Hammer2.1-1.5b"
CATEGORY = "multiple"
SAMPLE_SEED = "agentweave-bfcl-routing-pressure-v5:"
DISTRACTOR_SEED = "agentweave-bfcl-distractors-v5:"
SAMPLE_SIZE = 12
TARGET_TOOL_COUNT = 16
AGENTWEAVE_MAX_AGENTS = 4
AGENTWEAVE_MAX_TOOLS = 6
STRATEGIES = ("single-agent", "random-router", "semantic-router", "agentweave")

def load_jsonl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
def dump_jsonl(path,rows): Path(path).write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in rows)+"\n",encoding="utf-8")
def tool_name(fn): return str(fn.get("name",""))
def select_ids(data_file,n=SAMPLE_SIZE):
    rows=load_jsonl(data_file); ranked=sorted((hashlib.sha256((SAMPLE_SEED+r["id"]).encode()).hexdigest(),r["id"]) for r in rows)
    return sorted(i for _,i in ranked[:n])
def augment_rows(rows,sampled_ids):
    selected=set(sampled_ids); pool={}
    for row in rows:
        for fn in row.get("function") or []:
            if tool_name(fn): pool.setdefault(tool_name(fn),fn)
    output=[]; manifest={}
    for row in rows:
        clone=json.loads(json.dumps(row)); tid=row.get("id")
        if tid in selected:
            original=list(clone.get("function") or []); original_names={tool_name(x) for x in original}
            candidates=[fn for name,fn in pool.items() if name not in original_names]
            candidates.sort(key=lambda fn: hashlib.sha256((DISTRACTOR_SEED+tid+":"+tool_name(fn)).encode()).hexdigest())
            need=max(0,TARGET_TOOL_COUNT-len(original)); clone["function"]=original+candidates[:need]
            manifest[tid]={"original_tools":[tool_name(x) for x in original],"augmented_tools":[tool_name(x) for x in clone["function"]]}
        output.append(clone)
    return output,manifest
def wilson(s,n,z=1.959963984540054):
    if not n:return (0.,0.)
    p=s/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d;return max(0.,c-h),min(1.,c+h)
def exact_mcnemar(a,b):
    n10=sum(x and not y for x,y in zip(a,b));n01=sum((not x) and y for x,y in zip(a,b));n=n10+n01
    if n==0:return 1.0
    k=min(n10,n01);return min(1.0,2*sum(math.comb(n,i) for i in range(k+1))/(2**n))
def paired_bootstrap(a,b,seed=20260817,reps=10000):
    if not a:return (0.,0.)
    rng=random.Random(seed);n=len(a);v=[]
    for _ in range(reps):
        idx=[rng.randrange(n) for _ in range(n)];v.append(sum(a[i]-b[i] for i in idx)/n)
    v.sort();return v[int(.025*(reps-1))],v[int(.975*(reps-1))]
def read_score_rows(score_dir,sampled_ids):
    files=sorted(dict.fromkeys(list(Path(score_dir).rglob(f"*{CATEGORY}*score*.json"))+list(Path(score_dir).rglob(f"*{CATEGORY}*.json"))))
    for f in files:
        try: rows=load_jsonl(f)
        except Exception: continue
        if not rows: continue
        summary=next((r for r in rows if "correct_count" in r and "total_count" in r),None); detailed=[r for r in rows if r.get("id") is not None and "valid" in r]
        if not detailed and not summary: continue
        out={str(r["id"]):bool(r.get("valid")) for r in detailed};missing=set(sampled_ids)-set(out)
        if missing and summary:
            total=int(summary["total_count"]);correct=int(summary["correct_count"]);known_valid=sum(1 for i,v in out.items() if i in sampled_ids and v)
            if total==len(sampled_ids) and correct-known_valid==len(missing):out.update({i:True for i in missing});missing=set()
        if missing: raise RuntimeError(f"Missing sampled ids: {sorted(missing)}")
        if set(sampled_ids)<=set(out): return {i:out[i] for i in sampled_ids}
    raise RuntimeError(f"No BFCL per-task valid records for {CATEGORY}")
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
def run_strategy(strategy,bfcl_root,output_root,sampled_ids,port,data_file,original_rows,augmented_rows):
    run_root=output_root/strategy;run_root.mkdir(parents=True,exist_ok=True);(run_root/"test_case_ids_to_generate.json").write_text(json.dumps({CATEGORY:sampled_ids},indent=2))
    metrics=run_root/"provider_metrics.jsonl";env=os.environ.copy();env["BFCL_PROJECT_ROOT"]=str(run_root.resolve());env["OPENAI_API_KEY"]="local-no-key-shim";env["OPENAI_BASE_URL"]=f"http://127.0.0.1:{port}/v1";env["LOCAL_MODEL_BASE_URL"]="http://127.0.0.1:9100/v1";env["LOCAL_MODEL_ID"]=LOCAL_MODEL_ID
    proxy=subprocess.Popen([sys.executable,str((Path(__file__).parent/"bfcl_routing_proxy.py").resolve()),"--strategy",strategy,"--port",str(port),"--metrics",str(metrics.resolve()),"--max-agents",str(AGENTWEAVE_MAX_AGENTS),"--max-tools",str(AGENTWEAVE_MAX_TOOLS)],env=env)
    try:
        wait_http(f"http://127.0.0.1:{port}/v1/models",30)
        try:
            dump_jsonl(data_file,augmented_rows)
            subprocess.run(["bfcl","generate","--model",BFCL_HANDLER_MODEL_ID,"--run-ids","--num-threads","1","--include-input-log"],cwd=bfcl_root,env=env,check=True)
        finally: dump_jsonl(data_file,original_rows)
        subprocess.run(["bfcl","evaluate","--model",BFCL_HANDLER_MODEL_ID,"--test-category",CATEGORY,"--partial-eval"],cwd=bfcl_root,env=env,check=True)
    finally:
        proxy.terminate()
        try:proxy.wait(timeout=10)
        except subprocess.TimeoutExpired:proxy.kill()
    return read_score_rows(run_root/"score",sampled_ids),summarize_metrics(metrics)
def routing_diagnostics(original_rows,augmented_rows,sampled_ids):
    from scripts.bfcl_routing_proxy import Router,_tool_name
    original={r["id"]:r for r in original_rows if r.get("id") in sampled_ids}; augmented={r["id"]:r for r in augmented_rows if r.get("id") in sampled_ids};out={}
    for s in STRATEGIES:
        router=Router(s,max_agents=AGENTWEAVE_MAX_AGENTS,max_tools=AGENTWEAVE_MAX_TOOLS); cover=[]; selected_counts=[]
        for tid in sampled_ids:
            row=augmented[tid];q=row.get("question") or [];messages=q[0] if q and isinstance(q[0],list) else q;tools=[{"type":"function","function":fn} for fn in row.get("function") or []];chosen=router.select(messages,tools);chosen_names={_tool_name(t) for t in chosen};orig_names={tool_name(fn) for fn in original[tid].get("function") or []};cover.append(len(orig_names&chosen_names)/len(orig_names) if orig_names else 1.0);selected_counts.append(len(chosen))
        out[s]={"mean_original_candidate_recall":statistics.fmean(cover),"all_original_candidates_retained_rate":statistics.fmean(1.0 if x==1.0 else 0.0 for x in cover),"mean_selected_tools_pre_inference":statistics.fmean(selected_counts)}
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--bfcl-root",type=Path,required=True);ap.add_argument("--output",type=Path,default=Path("bfcl-native-live-results"));ap.add_argument("--protocol",type=Path,default=Path("evaluation/bfcl-native-live-v1.json"));ap.add_argument("--validate-only",action="store_true");args=ap.parse_args()
    protocol=json.loads(args.protocol.read_text());assert protocol["benchmark"]["commit"]=="6ea57973c7a6097fd7c5915698c54c17c5b1b6c8";assert protocol["benchmark"]["category"]==CATEGORY;assert protocol["benchmark"]["sample_size"]==SAMPLE_SIZE;assert protocol["benchmark"]["augmented_tool_count"]==TARGET_TOOL_COUNT;assert protocol["inference"]["model"]==LOCAL_MODEL_ID;assert protocol["strategies"]["agentweave"]["max_provider_agents"]==AGENTWEAVE_MAX_AGENTS;assert protocol["strategies"]["agentweave"]["max_tools"]==AGENTWEAVE_MAX_TOOLS;assert protocol["status"]=="preregistered-before-first-score"
    data=args.bfcl_root/"bfcl_eval"/"data"/f"BFCL_v4_{CATEGORY}.json";ids=select_ids(data);original_rows=load_jsonl(data);augmented_rows,manifest=augment_rows(original_rows,ids);args.output.mkdir(parents=True,exist_ok=True);(args.output/"sampled_ids.json").write_text(json.dumps(ids,indent=2));(args.output/"augmentation_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True))
    if args.validate_only:
        counts=[len(manifest[i]["augmented_tools"]) for i in ids];print(json.dumps({"protocol_valid":True,"study_id":protocol["study_id"],"category":CATEGORY,"sample_count":len(ids),"sample_sha256":hashlib.sha256("\n".join(ids).encode()).hexdigest(),"augmented_tool_count_min":min(counts),"augmented_tool_count_mean":statistics.fmean(counts),"agentweave_max_tools":AGENTWEAVE_MAX_TOOLS,"local_model":LOCAL_MODEL_ID},indent=2));return
    env=os.environ.copy();env["LOCAL_MODEL_ID"]=LOCAL_MODEL_ID;model_server=subprocess.Popen([sys.executable,str((Path(__file__).parent/"bfcl_local_hammer_server.py").resolve()),"--port","9100"],env=env)
    try:
        wait_http("http://127.0.0.1:9100/v1/models",900);score_maps={};metrics={}
        for idx,strategy in enumerate(STRATEGIES):score_maps[strategy],metrics[strategy]=run_strategy(strategy,args.bfcl_root,args.output,ids,8760+idx,data,original_rows,augmented_rows)
    finally:
        dump_jsonl(data,original_rows);model_server.terminate()
        try:model_server.wait(timeout=10)
        except subprocess.TimeoutExpired:model_server.kill()
    diagnostics=routing_diagnostics(original_rows,augmented_rows,ids);results={}
    for s in STRATEGIES:
        flags=[score_maps[s][i] for i in ids];succ=sum(flags);results[s]={"successes":succ,"n":len(flags),"native_task_success":succ/len(flags),"wilson_95_ci":list(wilson(succ,len(flags))),**metrics[s],**diagnostics[s]}
    comparisons={}
    for b in ("single-agent","random-router","semantic-router"):
        a=[float(score_maps["agentweave"][i]) for i in ids];bb=[float(score_maps[b][i]) for i in ids];comparisons[b]={"agentweave_minus_baseline_pp":100*(statistics.fmean(a)-statistics.fmean(bb)),"paired_bootstrap_95_ci_pp":[100*x for x in paired_bootstrap(a,bb)],"exact_mcnemar_p":exact_mcnemar([bool(x) for x in a],[bool(x) for x in bb])}
    payload={"study_id":protocol["study_id"],"category":CATEGORY,"benchmark_commit":protocol["benchmark"]["commit"],"model":LOCAL_MODEL_ID,"augmented_tool_count":TARGET_TOOL_COUNT,"sampled_ids":ids,"results":results,"comparisons":comparisons,"failure_index":[{"id":i,"strategy":s} for i in ids for s in STRATEGIES if not score_maps[s][i]],"evidence_boundary":protocol["evidence_boundary"]}
    (args.output/"summary.json").write_text(json.dumps(payload,indent=2,sort_keys=True));print(json.dumps(payload,indent=2,sort_keys=True))
if __name__=="__main__":main()
