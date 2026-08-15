from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from agentbench_external_eval import AGENTBENCH_PIN, DOMAIN_SPECS, build_agent_catalog, is_specialist_success, load_tasks
from agentweave.engine import AgentMatcher, PlacementEngine, TrustEngine
from agentweave.requirements import RequirementAnalyzer

COMMIT_CONFIDENCE = 0.65


def evaluate_selective(tasks: list[dict]) -> dict:
    """Blind confidence-aware routing on raw task text only.

    Labels are retained only as post-routing ground truth. AgentWeave commits when a
    specialist domain is inferred with sufficient confidence; otherwise it abstains.
    """
    agents = build_agent_catalog()
    matcher = AgentMatcher(TrustEngine(), PlacementEngine(), use_native=False)
    analyzer = RequirementAnalyzer()

    rows = []
    for task in tasks:
        req = analyzer.analyze(task["text"])
        started = time.perf_counter_ns()
        committed = bool(req.domains) and req.inference_confidence >= COMMIT_CONFIDENCE
        selected = matcher.rank(req, agents)[0].agent if committed else None
        elapsed_us = (time.perf_counter_ns() - started) / 1000.0
        rows.append({
            "domain_ground_truth": task["domain"],
            "task_id": task["id"],
            "committed": committed,
            "selected_agent": selected.agent_id if selected else None,
            "correct": bool(selected and is_specialist_success(selected, task["domain"])),
            "selection_compute_us": elapsed_us,
            "inferred_capabilities": sorted(req.capabilities),
            "inferred_domains": sorted(req.domains),
            "inferred_knowledge": sorted(req.knowledge),
            "inference_confidence": req.inference_confidence,
            "inference_source": req.inference_source,
            "ambiguity": req.ambiguity,
        })

    committed_rows = [r for r in rows if r["committed"]]
    correct = sum(r["correct"] for r in committed_rows)
    coverage = len(committed_rows) / max(1, len(rows))
    selective_accuracy = correct / max(1, len(committed_rows))
    end_to_end_correct_rate = correct / max(1, len(rows))

    per_domain = {}
    for domain in DOMAIN_SPECS:
        subset = [r for r in rows if r["domain_ground_truth"] == domain]
        committed_subset = [r for r in subset if r["committed"]]
        domain_correct = sum(r["correct"] for r in committed_subset)
        per_domain[domain] = {
            "tasks": len(subset),
            "committed": len(committed_subset),
            "coverage": len(committed_subset) / max(1, len(subset)),
            "selective_accuracy": domain_correct / max(1, len(committed_subset)),
            "correct_committed": domain_correct,
        }

    abstention_by_domain = defaultdict(int)
    for r in rows:
        if not r["committed"]:
            abstention_by_domain[r["domain_ground_truth"]] += 1

    return {
        "benchmark": "AgentBench blind confidence-aware selective routing",
        "agentbench_repository": "THUDM/AgentBench",
        "agentbench_commit": AGENTBENCH_PIN,
        "total_tasks": len(rows),
        "commit_confidence_threshold": COMMIT_CONFIDENCE,
        "committed_tasks": len(committed_rows),
        "abstained_tasks": len(rows) - len(committed_rows),
        "coverage": coverage,
        "selective_accuracy": selective_accuracy,
        "end_to_end_correct_rate": end_to_end_correct_rate,
        "mean_commit_compute_us": statistics.mean(r["selection_compute_us"] for r in committed_rows) if committed_rows else 0.0,
        "per_domain": per_domain,
        "abstentions_by_domain": dict(abstention_by_domain),
        "protocol_boundary": {
            "router_input": "Raw published AgentBench task text only.",
            "withheld": "AgentBench environment/domain label and expected specialist identity during routing.",
            "confidence_rule": f"Commit only when generic RequirementAnalyzer infers a specialist domain with confidence >= {COMMIT_CONFIDENCE:.2f}; otherwise abstain.",
            "ground_truth": "AgentBench domain label is used only after routing to score the committed specialist.",
            "external_data": "Published AgentBench task text and held-out domain labels.",
            "synthetic_data": "Candidate agent catalog, trust, proficiency, latency and cost values.",
            "not_measured": "Not original AgentBench task-completion success, LLM answer quality, provider latency, or billed cost.",
        },
        "raw": rows,
    }


def markdown_report(result: dict) -> str:
    lines = [
        "# AgentBench blind confidence-aware selective routing",
        "",
        f"Pinned AgentBench commit: `{result['agentbench_commit']}`",
        f"Tasks: **{result['total_tasks']}**",
        "",
        f"**Protocol:** raw task text only; labels are hidden during routing. AgentWeave commits only with a specialist domain and confidence >= **{result['commit_confidence_threshold']:.2f}**.",
        "",
        f"- Coverage: **{100*result['coverage']:.1f}%** ({result['committed_tasks']} committed / {result['total_tasks']} total)",
        f"- Selective accuracy on committed tasks: **{100*result['selective_accuracy']:.1f}%**",
        f"- Correct specialist over all tasks: **{100*result['end_to_end_correct_rate']:.1f}%**",
        f"- Abstained tasks: **{result['abstained_tasks']}**",
        f"- Mean compute for committed routes: **{result['mean_commit_compute_us']:.1f} us**",
        "",
        "## Per-domain selective routing",
        "",
        "| Domain | Tasks | Committed | Coverage | Accuracy when committed |",
        "|---|---:|---:|---:|---:|",
    ]
    for domain, row in result["per_domain"].items():
        lines.append(f"| {domain} | {row['tasks']} | {row['committed']} | {100*row['coverage']:.1f}% | {100*row['selective_accuracy']:.1f}% |")
    lines += [
        "",
        "## Interpretation boundary",
        "",
        "- This measures whether AgentWeave can infer enough task intent to commit to a specialist.",
        "- Abstention is intentional and is not counted as a correct route.",
        "- The benchmark label is never used to decide whether to commit or which agent to choose.",
        "- Built-in lexical and semantic-intent inference is benchmark-label independent; an optional external semantic/LLM inferencer can be plugged in separately.",
        "- This is still a routing evaluation, not original AgentBench end-to-end environment success.",
        "",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agentbench-root", required=True)
    p.add_argument("--per-domain", type=int, default=200)
    p.add_argument("--json-out", default="agentbench-selective-results.json")
    p.add_argument("--md-out", default="agentbench-selective-results.md")
    args = p.parse_args()

    tasks = load_tasks(Path(args.agentbench_root), args.per_domain)
    result = evaluate_selective(tasks)
    Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    report = markdown_report(result)
    Path(args.md_out).write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
