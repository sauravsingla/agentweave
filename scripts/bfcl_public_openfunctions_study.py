from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import time
from pathlib import Path

from scripts.bfcl_routing_proxy import Router

MODEL_ID = "gorilla-openfunctions-v2"
CATEGORY = "multiple"
SAMPLE_SEED = "agentweave-bfcl-public-v3:"
STRATEGIES = ("single-agent", "semantic-router", "agentweave")


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dump_jsonl(path: Path, rows):
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def select_ids(data_file: Path, n: int = 12):
    rows = load_jsonl(data_file)
    ranked = sorted(
        (hashlib.sha256((SAMPLE_SEED + row["id"]).encode()).hexdigest(), row["id"])
        for row in rows
    )
    return sorted(task_id for _, task_id in ranked[:n])


def wilson(successes, n, z=1.959963984540054):
    if not n:
        return 0.0, 0.0
    p = successes / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
    return max(0.0, c - h), min(1.0, c + h)


def exact_mcnemar(a, b):
    n10 = sum(x and not y for x, y in zip(a, b))
    n01 = sum((not x) and y for x, y in zip(a, b))
    n = n10 + n01
    if n == 0:
        return 1.0
    k = min(n10, n01)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2**n))


def paired_bootstrap(a, b, seed=20260817, reps=10000):
    if not a:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(a)
    values = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        values.append(sum(a[i] - b[i] for i in idx) / n)
    values.sort()
    return values[int(.025 * (reps - 1))], values[int(.975 * (reps - 1))]


def question_messages(row):
    question = row.get("question") or []
    if question and isinstance(question[0], list):
        return question[0]
    return question


def filtered_rows(original_rows, sampled_ids, strategy):
    router = Router(strategy)
    selected_ids = set(sampled_ids)
    output = []
    counts = {}
    for row in original_rows:
        clone = json.loads(json.dumps(row))
        if row.get("id") in selected_ids:
            functions = list(row.get("function") or [])
            tools = [{"type": "function", "function": function} for function in functions]
            chosen = router.select(question_messages(row), tools)
            clone["function"] = [tool["function"] for tool in chosen]
            counts[row["id"]] = {"before": len(functions), "after": len(chosen)}
        output.append(clone)
    return output, counts


def read_score_rows(score_dir: Path, sampled_ids):
    files = sorted(dict.fromkeys(
        list(score_dir.rglob(f"*{CATEGORY}*score*.json")) + list(score_dir.rglob(f"*{CATEGORY}*.json"))
    ))
    rows = []
    for file in files:
        try:
            candidate = load_jsonl(file)
        except Exception:
            continue
        if candidate and any("valid" in row for row in candidate):
            rows = candidate
            break
    if not rows:
        raise RuntimeError(f"No BFCL per-task valid records for {CATEGORY}")
    out = {str(row["id"]): bool(row.get("valid")) for row in rows if row.get("id") is not None}
    if not out and len(rows) == len(sampled_ids):
        out = {task_id: bool(row.get("valid")) for task_id, row in zip(sampled_ids, rows)}
    missing = set(sampled_ids) - set(out)
    if missing:
        raise RuntimeError(f"Missing sampled ids: {sorted(missing)}")
    return {task_id: out[task_id] for task_id in sampled_ids}


def run_strategy(strategy, bfcl_root, output_root, sampled_ids, data_file, original_rows):
    run_root = output_root / strategy
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "test_case_ids_to_generate.json").write_text(
        json.dumps({CATEGORY: sampled_ids}, indent=2), encoding="utf-8"
    )
    routed_rows, counts = filtered_rows(original_rows, sampled_ids, strategy)
    env = os.environ.copy()
    env["BFCL_PROJECT_ROOT"] = str(run_root.resolve())
    started = time.perf_counter()
    try:
        dump_jsonl(data_file, routed_rows)
        subprocess.run(
            ["bfcl", "generate", "--model", MODEL_ID, "--run-ids", "--num-threads", "1", "--include-input-log"],
            cwd=bfcl_root,
            env=env,
            check=True,
        )
    finally:
        dump_jsonl(data_file, original_rows)
    subprocess.run(
        ["bfcl", "evaluate", "--model", MODEL_ID, "--test-category", CATEGORY, "--partial-eval"],
        cwd=bfcl_root,
        env=env,
        check=True,
    )
    elapsed = time.perf_counter() - started
    score_map = read_score_rows(run_root / "score", sampled_ids)
    before = [counts[i]["before"] for i in sampled_ids]
    after = [counts[i]["after"] for i in sampled_ids]
    return score_map, {
        "elapsed_seconds": elapsed,
        "mean_tools_before": statistics.fmean(before),
        "mean_tools_after": statistics.fmean(after),
        "external_api_spend_usd": 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bfcl-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("bfcl-public-openfunctions-results"))
    parser.add_argument("--protocol", type=Path, default=Path("evaluation/bfcl-public-openfunctions-v3.json"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    assert protocol["status"] == "preregistered-before-first-score"
    assert protocol["benchmark"]["commit"] == "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
    assert protocol["benchmark"]["category"] == CATEGORY
    assert protocol["benchmark"]["sample_size"] == 12
    assert protocol["inference"]["model"] == MODEL_ID

    data_file = args.bfcl_root / "bfcl_eval" / "data" / f"BFCL_v4_{CATEGORY}.json"
    sampled_ids = select_ids(data_file, 12)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "sampled_ids.json").write_text(json.dumps(sampled_ids, indent=2), encoding="utf-8")
    if args.validate_only:
        print(json.dumps({
            "protocol_valid": True,
            "study_id": protocol["study_id"],
            "category": CATEGORY,
            "sample_count": len(sampled_ids),
            "sample_sha256": hashlib.sha256("\n".join(sampled_ids).encode()).hexdigest(),
            "model": MODEL_ID,
        }, indent=2))
        return

    original_rows = load_jsonl(data_file)
    score_maps = {}
    metrics = {}
    for strategy in STRATEGIES:
        score_maps[strategy], metrics[strategy] = run_strategy(
            strategy, args.bfcl_root, args.output, sampled_ids, data_file, original_rows
        )

    results = {}
    for strategy in STRATEGIES:
        flags = [score_maps[strategy][task_id] for task_id in sampled_ids]
        successes = sum(flags)
        results[strategy] = {
            "successes": successes,
            "n": len(flags),
            "native_task_success": successes / len(flags),
            "wilson_95_ci": list(wilson(successes, len(flags))),
            **metrics[strategy],
        }

    comparisons = {}
    for baseline in ("single-agent", "semantic-router"):
        agentweave = [float(score_maps["agentweave"][task_id]) for task_id in sampled_ids]
        other = [float(score_maps[baseline][task_id]) for task_id in sampled_ids]
        ci = paired_bootstrap(agentweave, other)
        comparisons[baseline] = {
            "agentweave_minus_baseline_pp": 100 * (statistics.fmean(agentweave) - statistics.fmean(other)),
            "paired_bootstrap_95_ci_pp": [100 * ci[0], 100 * ci[1]],
            "exact_mcnemar_p": exact_mcnemar([bool(x) for x in agentweave], [bool(x) for x in other]),
        }

    payload = {
        "study_id": protocol["study_id"],
        "benchmark_commit": protocol["benchmark"]["commit"],
        "category": CATEGORY,
        "model": MODEL_ID,
        "sampled_ids": sampled_ids,
        "results": results,
        "comparisons": comparisons,
        "failure_index": [
            {"id": task_id, "strategy": strategy}
            for task_id in sampled_ids
            for strategy in STRATEGIES
            if not score_maps[strategy][task_id]
        ],
        "evidence_boundary": protocol["evidence_boundary"],
    }
    (args.output / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
