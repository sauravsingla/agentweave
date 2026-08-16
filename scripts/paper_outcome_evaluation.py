from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from research.paper_stats import exact_mcnemar_pvalue, paired_bootstrap_difference, wilson_interval
from scripts.team_advantage_benchmark import DEFAULT_SEED, run_benchmark


STRATEGIES = ("agentweave-team", "single-best-agent", "random-team", "capability-only-team")


async def collect(seed_count: int) -> list[dict]:
    rows: list[dict] = []
    for offset in range(seed_count):
        seed = DEFAULT_SEED + offset
        payload = await run_benchmark(seed)
        for row in payload["tasks"]:
            rows.append({"seed": seed, **row})
    return rows


def summarize(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["strategy"]].append(row)
    result = {}
    for strategy in STRATEGIES:
        items = grouped[strategy]
        completions = [bool(i["completion"]) for i in items]
        lo, hi = wilson_interval(sum(completions), len(completions))
        recovery = [i for i in items if int(i["failures"]) > 0]
        result[strategy] = {
            "observations": len(items),
            "completion_rate": sum(completions) / len(completions),
            "completion_wilson_95": [lo, hi],
            "mean_quality": fmean(float(i["quality"]) for i in items),
            "mean_cost": fmean(float(i["cost"]) for i in items),
            "mean_latency_ms": fmean(float(i["latency_ms"]) for i in items),
            "recovery_opportunities": len(recovery),
            "recovery_success_rate": (
                sum(bool(i["recovered"]) for i in recovery) / len(recovery) if recovery else None
            ),
        }
    return result


def paired(rows: list[dict], comparator: str) -> dict:
    aw = {(r["seed"], r["task_id"]): r for r in rows if r["strategy"] == "agentweave-team"}
    other = {(r["seed"], r["task_id"]): r for r in rows if r["strategy"] == comparator}
    keys = sorted(set(aw) & set(other))
    aw_completion = [bool(aw[k]["completion"]) for k in keys]
    other_completion = [bool(other[k]["completion"]) for k in keys]
    return {
        "pairs": len(keys),
        "completion": {
            "agentweave_minus_baseline": paired_bootstrap_difference(
                [float(v) for v in aw_completion], [float(v) for v in other_completion]
            ),
            "mcnemar_exact": exact_mcnemar_pvalue(aw_completion, other_completion),
        },
        "quality": {
            "agentweave_minus_baseline": paired_bootstrap_difference(
                [float(aw[k]["quality"]) for k in keys], [float(other[k]["quality"]) for k in keys]
            )
        },
        "cost": {
            "agentweave_minus_baseline": paired_bootstrap_difference(
                [float(aw[k]["cost"]) for k in keys], [float(other[k]["cost"]) for k in keys]
            )
        },
        "latency_ms": {
            "agentweave_minus_baseline": paired_bootstrap_difference(
                [float(aw[k]["latency_ms"]) for k in keys], [float(other[k]["latency_ms"]) for k in keys]
            )
        },
    }


def hypothesis_status(summary: dict, comparisons: dict) -> dict:
    aw = summary["agentweave-team"]
    h1 = all(
        comparisons[name]["completion"]["agentweave_minus_baseline"]["difference"] >= 0.20
        for name in STRATEGIES[1:]
    )
    h2 = all(
        comparisons[name]["quality"]["agentweave_minus_baseline"]["difference"] >= 0.10
        for name in STRATEGIES[1:]
    )
    h3 = aw["recovery_success_rate"] is not None and aw["recovery_success_rate"] >= 0.90
    return {"H1": h1, "H2": h2, "H3": h3}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--json-out", type=Path, default=Path("paper-outcome-results.json"))
    parser.add_argument("--md-out", type=Path, default=Path("paper-outcome-results.md"))
    args = parser.parse_args()
    if args.seeds != 30:
        raise SystemExit("paper-quality-v1 protocol preregisters exactly 30 seeds")

    rows = asyncio.run(collect(args.seeds))
    summary = summarize(rows)
    comparisons = {name: paired(rows, name) for name in STRATEGIES[1:]}
    hypotheses = hypothesis_status(summary, comparisons)
    failures = [
        r for r in rows
        if (r["strategy"] == "agentweave-team" and not r["completion"])
        or int(r["failures"]) > 0
    ]
    result = {
        "protocol": "evaluation/paper-quality-v1.json",
        "seed_count": args.seeds,
        "workloads_per_seed": 12,
        "summary": summary,
        "paired_comparisons": comparisons,
        "hypotheses_supported": hypotheses,
        "failure_and_recovery_cases": failures,
        "evidence_boundary": "Actual task completion from controlled executable handlers over a synthetic agent catalog; not production-user or external-provider task success.",
    }
    args.json_out.write_text(json.dumps(result, indent=2) + "\n")

    lines = [
        "# Paper-quality confirmatory outcome evaluation",
        "",
        "Hypotheses and the 30-seed design were committed in `evaluation/paper-quality-v1.json` before this confirmatory run.",
        "",
        "| Strategy | Observations | Completion | Wilson 95% CI | Mean quality | Mean cost | Mean latency | Recovery |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for strategy in STRATEGIES:
        item = summary[strategy]
        lo, hi = item["completion_wilson_95"]
        recovery = "n/a" if item["recovery_success_rate"] is None else f"{100*item['recovery_success_rate']:.1f}%"
        lines.append(
            f"| {strategy} | {item['observations']} | {100*item['completion_rate']:.1f}% | [{100*lo:.1f}%, {100*hi:.1f}%] | {item['mean_quality']:.3f} | {item['mean_cost']:.3f} | {item['mean_latency_ms']:.1f} ms | {recovery} |"
        )
    lines += ["", "## Preregistered hypotheses", ""]
    for hypothesis, supported in hypotheses.items():
        lines.append(f"- **{hypothesis}: {'SUPPORTED' if supported else 'NOT SUPPORTED'}**")
    lines += ["", "## Paired comparisons", ""]
    for name, comp in comparisons.items():
        d = comp["completion"]["agentweave_minus_baseline"]
        p = comp["completion"]["mcnemar_exact"]["p_value"]
        q = comp["quality"]["agentweave_minus_baseline"]
        lines.append(
            f"- vs `{name}`: completion Δ={100*d['difference']:+.1f} pp, bootstrap 95% CI [{100*d['ci_low']:+.1f}, {100*d['ci_high']:+.1f}] pp, McNemar p={p:.6g}; quality Δ={q['difference']:+.3f}, 95% CI [{q['ci_low']:+.3f}, {q['ci_high']:+.3f}]."
        )
    lines += [
        "",
        f"Failure/recovery rows retained in JSON: **{len(failures)}**.",
        "",
        "**Boundary:** these are genuine executed outcomes inside the controlled benchmark, but the agent catalog, costs, latency profiles, and injected failures are synthetic. They are not external production task-success measurements.",
    ]
    args.md_out.write_text("\n".join(lines) + "\n")
    print(args.md_out.read_text())


if __name__ == "__main__":
    main()
