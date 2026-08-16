from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path


MODEL_ID = "gpt-4.1-mini-2025-04-14-FC"
CATEGORY = "multi_turn_base"
SAMPLE_SEED = "agentweave-bfcl-native-v1:"
STRATEGIES = ("single-agent", "semantic-router", "agentweave")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def select_ids(data_file: Path, n: int = 60) -> list[str]:
    rows = load_jsonl(data_file)
    ranked = sorted(
        (hashlib.sha256((SAMPLE_SEED + row["id"]).encode()).hexdigest(), row["id"])
        for row in rows
    )
    return sorted(item_id for _, item_id in ranked[:n])


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
    return max(0.0, c - h), min(1.0, c + h)


def exact_mcnemar(a: list[bool], b: list[bool]) -> float:
    n10 = sum(x and not y for x, y in zip(a, b))
    n01 = sum((not x) and y for x, y in zip(a, b))
    n = n10 + n01
    if n == 0:
        return 1.0
    k = min(n10, n01)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def paired_bootstrap(a: list[float], b: list[float], seed: int = 20260816, reps: int = 10000) -> tuple[float, float]:
    if not a:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(a)
    vals = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        vals.append(sum(a[i] - b[i] for i in idx) / n)
    vals.sort()
    return vals[int(.025 * (reps - 1))], vals[int(.975 * (reps - 1))]


def read_score_rows(score_dir: Path, sampled_ids: list[str]) -> dict[str, bool]:
    files = list(score_dir.rglob("*multi_turn_base*score*.json")) + list(score_dir.rglob("*multi_turn_base*.json"))
    files = sorted(dict.fromkeys(files))
    if not files:
        raise FileNotFoundError(f"No BFCL multi-turn score JSON found under {score_dir}")
    rows: list[dict] = []
    for file in files:
        try:
            candidate = load_jsonl(file)
        except Exception:
            continue
        if candidate and any("valid" in row for row in candidate):
            rows = candidate
            break
    if not rows:
        raise RuntimeError("BFCL score file contained no per-task valid records")
    out: dict[str, bool] = {}
    ids_with_values = [str(r.get("id")) for r in rows if r.get("id") is not None]
    if ids_with_values:
        for row in rows:
            if row.get("id") is not None:
                out[str(row["id"])] = bool(row.get("valid"))
    else:
        if len(rows) != len(sampled_ids):
            raise RuntimeError(f"Cannot align {len(rows)} score rows with {len(sampled_ids)} sampled ids")
        for item_id, row in zip(sampled_ids, rows):
            out[item_id] = bool(row.get("valid"))
    missing = set(sampled_ids) - set(out)
    if missing:
        raise RuntimeError(f"Missing {len(missing)} sampled ids in BFCL score output")
    return {i: out[i] for i in sampled_ids}


def summarize_metrics(path: Path) -> dict:
    rows = load_jsonl(path) if path.exists() else []
    successful = [r for r in rows if int(r.get("http_status", 500)) < 400]
    return {
        "api_calls": len(rows),
        "successful_api_calls": len(successful),
        "mean_call_latency_seconds": statistics.fmean(r["latency_seconds"] for r in rows) if rows else 0.0,
        "median_call_latency_seconds": statistics.median(r["latency_seconds"] for r in rows) if rows else 0.0,
        "input_tokens": sum(int(r.get("input_tokens", 0)) for r in rows),
        "cached_input_tokens": sum(int(r.get("cached_input_tokens", 0)) for r in rows),
        "output_tokens": sum(int(r.get("output_tokens", 0)) for r in rows),
        "usage_priced_cost_usd": sum(float(r.get("usage_priced_cost_usd", 0.0)) for r in rows),
        "mean_tools_before": statistics.fmean(r["tools_before"] for r in rows) if rows else 0.0,
        "mean_tools_after": statistics.fmean(r["tools_after"] for r in rows) if rows else 0.0,
        "provider_errors": [r for r in rows if r.get("error")],
    }


def wait_proxy(port: int, timeout: float = 30.0) -> None:
    import httpx
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=1).status_code == 200:
                return
        except Exception:
            time.sleep(.25)
    raise RuntimeError(f"Proxy on port {port} did not become ready")


def run_strategy(strategy: str, bfcl_root: Path, output_root: Path, sampled_ids: list[str], port: int) -> tuple[dict[str, bool], dict]:
    run_root = output_root / strategy
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "test_case_ids_to_generate.json").write_text(json.dumps({CATEGORY: sampled_ids}, indent=2))
    metrics_path = run_root / "provider_metrics.jsonl"
    env = os.environ.copy()
    env["BFCL_PROJECT_ROOT"] = str(run_root.resolve())
    env["OPENAI_API_KEY"] = "agentweave-routing-proxy"
    env["OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
    env["UPSTREAM_OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY_LIVE"]
    proxy = subprocess.Popen(
        [sys.executable, str((Path(__file__).parent / "bfcl_routing_proxy.py").resolve()), "--strategy", strategy, "--port", str(port), "--metrics", str(metrics_path.resolve())],
        env=env,
    )
    try:
        wait_proxy(port)
        subprocess.run(
            ["bfcl", "generate", "--model", MODEL_ID, "--run-ids", "--num-threads", "1", "--include-input-log"],
            cwd=bfcl_root,
            env=env,
            check=True,
        )
        subprocess.run(
            ["bfcl", "evaluate", "--model", MODEL_ID, "--test-category", CATEGORY, "--partial-eval"],
            cwd=bfcl_root,
            env=env,
            check=True,
        )
    finally:
        proxy.terminate()
        try:
            proxy.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proxy.kill()
    return read_score_rows(run_root / "score", sampled_ids), summarize_metrics(metrics_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bfcl-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("bfcl-native-live-results"))
    parser.add_argument("--protocol", type=Path, default=Path("evaluation/bfcl-native-live-v1.json"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    assert protocol["benchmark"]["commit"] == "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
    assert protocol["benchmark"]["sample_size"] == 60
    assert protocol["provider"]["model"] == "gpt-4.1-mini-2025-04-14"
    assert protocol["status"] == "preregistered-before-first-score"
    data_file = args.bfcl_root / "bfcl_eval" / "data" / "BFCL_v4_multi_turn_base.json"
    sampled_ids = select_ids(data_file, protocol["benchmark"]["sample_size"])
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "sampled_ids.json").write_text(json.dumps(sampled_ids, indent=2))
    if args.validate_only:
        print(json.dumps({"protocol_valid": True, "sample_count": len(sampled_ids), "sample_sha256": hashlib.sha256("\n".join(sampled_ids).encode()).hexdigest()}, indent=2))
        return
    if not os.environ.get("OPENAI_API_KEY_LIVE"):
        raise SystemExit("OPENAI_API_KEY_LIVE is required. The preregistered study is intentionally not replaced with synthetic provider measurements.")

    score_maps: dict[str, dict[str, bool]] = {}
    metrics: dict[str, dict] = {}
    for idx, strategy in enumerate(STRATEGIES):
        score_maps[strategy], metrics[strategy] = run_strategy(strategy, args.bfcl_root, args.output, sampled_ids, 8760 + idx)

    results = {}
    for strategy in STRATEGIES:
        flags = [score_maps[strategy][i] for i in sampled_ids]
        successes = sum(flags)
        ci = wilson(successes, len(flags))
        results[strategy] = {
            "successes": successes,
            "n": len(flags),
            "native_task_success": successes / len(flags),
            "wilson_95_ci": list(ci),
            **metrics[strategy],
        }
    comparisons = {}
    for baseline in ("single-agent", "semantic-router"):
        a = [float(score_maps["agentweave"][i]) for i in sampled_ids]
        b = [float(score_maps[baseline][i]) for i in sampled_ids]
        comparisons[baseline] = {
            "agentweave_minus_baseline_pp": 100 * (statistics.fmean(a) - statistics.fmean(b)),
            "paired_bootstrap_95_ci_pp": [100 * x for x in paired_bootstrap(a, b)],
            "exact_mcnemar_p": exact_mcnemar([bool(x) for x in a], [bool(x) for x in b]),
        }
    failures = []
    for item_id in sampled_ids:
        for strategy in STRATEGIES:
            if not score_maps[strategy][item_id]:
                failures.append({"id": item_id, "strategy": strategy})
    payload = {
        "study_id": protocol["study_id"],
        "benchmark_commit": protocol["benchmark"]["commit"],
        "model": protocol["provider"]["model"],
        "sampled_ids": sampled_ids,
        "results": results,
        "comparisons": comparisons,
        "failure_index": failures,
        "evidence_boundary": protocol["evidence_boundary"],
    }
    out = args.output / "summary.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
