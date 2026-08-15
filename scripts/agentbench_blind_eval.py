from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from agentbench_external_eval import (
    AGENTBENCH_PIN,
    DOMAIN_SPECS,
    build_agent_catalog,
    capability_only,
    fixed_single_best,
    is_specialist_success,
    load_tasks,
    trust_only,
)
from agentweave.engine import AgentMatcher, PlacementEngine, TrustEngine
from agentweave.requirements import RequirementAnalyzer


def evaluate_blind(tasks: list[dict], seed: int = 17) -> dict:
    """Evaluate text-only routing with AgentBench labels hidden from the router.

    The published AgentBench environment/domain label is retained only as the
    post-selection ground truth. AgentWeave and every task-aware baseline receive
    a Requirement inferred from raw task text by AgentWeave's RequirementAnalyzer.
    """
    agents = build_agent_catalog()
    matcher = AgentMatcher(TrustEngine(), PlacementEngine(), use_native=False)
    analyzer = RequirementAnalyzer()
    rng = random.Random(seed)
    fixed_agent = fixed_single_best(agents)
    methods = {name: [] for name in ("agentweave", "single-best", "random", "capability-only", "trust-only")}

    for task in tasks:
        # Critical blind boundary: do not pass task["domain"] into requirement inference.
        req = analyzer.analyze(task["text"])
        selectors = {
            "agentweave": lambda: matcher.rank(req, agents)[0].agent,
            "single-best": lambda: fixed_agent,
            "random": lambda: rng.choice(agents),
            "capability-only": lambda: capability_only(req, agents),
            "trust-only": lambda: trust_only(agents),
        }
        for method, select in selectors.items():
            started = time.perf_counter_ns()
            selected = select()
            elapsed_us = (time.perf_counter_ns() - started) / 1000.0
            methods[method].append({
                "domain_ground_truth": task["domain"],
                "task_id": task["id"],
                "selected_agent": selected.agent_id,
                "specialist_selection_success": is_specialist_success(selected, task["domain"]),
                "selection_compute_us": elapsed_us,
                "catalog_latency_ms": selected.execution.latency_ms,
                "catalog_cost": selected.execution.cost,
                "inferred_capabilities": sorted(req.capabilities),
                "inferred_domains": sorted(req.domains),
                "inferred_knowledge": sorted(req.knowledge),
            })

    def summarize(rows: list[dict]) -> dict:
        return {
            "tasks": len(rows),
            "specialist_selection_rate": sum(r["specialist_selection_success"] for r in rows) / max(1, len(rows)),
            "mean_selection_compute_us": statistics.mean(r["selection_compute_us"] for r in rows),
            "mean_catalog_latency_ms": statistics.mean(r["catalog_latency_ms"] for r in rows),
            "mean_catalog_cost": statistics.mean(r["catalog_cost"] for r in rows),
        }

    aggregate = {name: summarize(rows) for name, rows in methods.items()}
    per_domain = {}
    for name, rows in methods.items():
        per_domain[name] = {}
        for domain in DOMAIN_SPECS:
            subset = [r for r in rows if r["domain_ground_truth"] == domain]
            if subset:
                per_domain[name][domain] = summarize(subset)

    confusion = defaultdict(Counter)
    for row in methods["agentweave"]:
        confusion[row["domain_ground_truth"]][row["selected_agent"]] += 1

    inferred_capabilities = Counter()
    for row in methods["agentweave"]:
        inferred_capabilities.update(row["inferred_capabilities"])

    counts = {domain: sum(t["domain"] == domain for t in tasks) for domain in DOMAIN_SPECS}
    return {
        "benchmark": "AgentBench blind text-only routing evaluation",
        "agentbench_repository": "THUDM/AgentBench",
        "agentbench_commit": AGENTBENCH_PIN,
        "task_counts": counts,
        "total_tasks": len(tasks),
        "blind_protocol": {
            "router_input": "Raw published AgentBench task text only.",
            "withheld_from_router": "AgentBench environment/domain label, synthetic specialist identity, expected capability set and expected knowledge set.",
            "ground_truth_use": "The AgentBench environment/domain label is used only after selection to score whether the matching synthetic specialist was selected.",
            "requirement_inference": "AgentWeave RequirementAnalyzer from agentweave/requirements.py; no benchmark-specific classifier or label mapping is used in the blind path.",
        },
        "metric_boundary": {
            "external_real_data": "Published AgentBench task descriptions and environment labels from DBBench, KnowledgeGraph and OS Interaction.",
            "synthetic_data": "Candidate agent catalog, proficiencies, validation flags, trust, latency and cost values.",
            "success_metric": "Blind specialist-selection rate after text-only requirement inference.",
            "not_measured": "This is not original AgentBench end-to-end task-completion success rate; no LLM or AgentBench environment execution is performed.",
            "real_timing": "selection_compute_us is measured wall-clock routing computation in this run.",
            "proxy_timing_cost": "catalog_latency_ms and catalog_cost remain fixed synthetic catalog attributes.",
        },
        "aggregate": aggregate,
        "per_domain": per_domain,
        "agentweave_confusion": {k: dict(v) for k, v in confusion.items()},
        "agentweave_inferred_capability_counts": dict(inferred_capabilities),
        "raw": methods,
    }


def markdown_report(result: dict) -> str:
    lines = [
        "# AgentBench blind text-only routing evaluation",
        "",
        f"Pinned AgentBench commit: `{result['agentbench_commit']}`",
        f"Tasks: **{result['total_tasks']}** — " + ", ".join(f"{k}: {v}" for k, v in result["task_counts"].items()),
        "",
        "**Blind protocol:** the router receives only raw AgentBench task text. The published environment/domain label is hidden during selection and used only afterward as ground truth.",
        "",
        "| Method | Blind specialist selection | Router compute | Catalog latency proxy | Catalog cost proxy |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, row in result["aggregate"].items():
        lines.append(
            f"| {name} | {100*row['specialist_selection_rate']:.1f}% | "
            f"{row['mean_selection_compute_us']:.1f} us | {row['mean_catalog_latency_ms']:.1f} ms | {row['mean_catalog_cost']:.3f} |"
        )

    lines += ["", "## AgentWeave per-domain blind accuracy", ""]
    aw = result["per_domain"]["agentweave"]
    for domain, row in aw.items():
        lines.append(f"- **{domain}:** {100*row['specialist_selection_rate']:.1f}% ({row['tasks']} tasks)")

    lines += ["", "## AgentWeave selection confusion", ""]
    for domain, selected in result["agentweave_confusion"].items():
        detail = ", ".join(f"{agent}={count}" for agent, count in sorted(selected.items()))
        lines.append(f"- **{domain}:** {detail}")

    cap_counts = result["agentweave_inferred_capability_counts"]
    lines += [
        "",
        "## Requirement-inference diagnostic",
        "",
        "Capabilities inferred from raw text across tasks: " + (", ".join(f"{k}={v}" for k, v in sorted(cap_counts.items())) or "none"),
        "",
        "## Interpretation boundary",
        "",
        "- **External data:** raw task text and held-out ground-truth environment labels come from the official AgentBench repository.",
        "- **Blind routing:** no AgentBench domain label or benchmark-specific expected capability mapping is passed to AgentWeave during selection.",
        "- **Synthetic catalog:** candidate agents, trust, proficiency, latency and cost are fixed synthetic values.",
        "- **Real measurement:** router compute latency is measured during this run.",
        "- **Not claimed:** original AgentBench task-completion SR, model answer quality, real provider latency, or billed model cost.",
        "",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agentbench-root", required=True)
    p.add_argument("--per-domain", type=int, default=200)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--json-out", default="agentbench-blind-results.json")
    p.add_argument("--md-out", default="agentbench-blind-results.md")
    args = p.parse_args()

    tasks = load_tasks(Path(args.agentbench_root), args.per_domain)
    result = evaluate_blind(tasks, args.seed)
    Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    report = markdown_report(result)
    Path(args.md_out).write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
