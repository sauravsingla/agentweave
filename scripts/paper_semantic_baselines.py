from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from scripts.paper_stats import exact_mcnemar_pvalue, paired_bootstrap_difference, wilson_interval
from scripts.untouched_generalization import evaluate as evaluate_frozen
from scripts.untouched_generalization import load_manifest, load_tasks, verify_router_frozen


FAMILY_DESCRIPTIONS = {
    "mathhay": "mathematics, arithmetic, algebra, geometry, proofs, quantitative problem solving",
    "mcpbench": "tool use, APIs, function calling, MCP servers, external tools and integrations",
    "search": "web search, information retrieval, research, factual lookup, multi-source investigation",
    "swebench": "software engineering, programming, debugging, repositories, code changes, tests",
    "tau2bench": "customer service, policy compliance, eligibility, transactions, procedural support",
    "terminalbench": "operating systems, command line, shell, browser or computer interaction, state-changing actions",
}


def semantic_predictions(tasks: list[dict], model_name: str) -> list[dict]:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    families = list(FAMILY_DESCRIPTIONS)
    descriptions = [FAMILY_DESCRIPTIONS[f] for f in families]
    description_vectors = model.encode(descriptions, normalize_embeddings=True, show_progress_bar=False)
    task_vectors = model.encode([t["text"] for t in tasks], normalize_embeddings=True, show_progress_bar=False)
    rows = []
    for task, vector in zip(tasks, task_vectors):
        scores = [float(vector @ desc) for desc in description_vectors]
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        rows.append({
            "task_id": task["task_id"],
            "truth": task["family"],
            "predicted_family": families[best_idx],
            "correct": families[best_idx] == task["family"],
            "score": scores[best_idx],
        })
    return rows


def score(rows: list[dict]) -> dict:
    correct = sum(bool(r["correct"]) for r in rows)
    low, high = wilson_interval(correct, len(rows))
    by_family: dict[str, list[bool]] = defaultdict(list)
    confusion: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_family[row["truth"]].append(bool(row["correct"]))
        confusion[row["truth"]][row["predicted_family"]] += 1
    return {
        "tasks": len(rows),
        "hit_at_1": correct / len(rows),
        "wilson_95": [low, high],
        "per_family": {
            family: sum(values) / len(values) if values else None
            for family, values in by_family.items()
        },
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=["sentence-transformers/all-MiniLM-L6-v2", "BAAI/bge-small-en-v1.5"])
    parser.add_argument("--json-out", type=Path, default=Path("paper-semantic-baselines.json"))
    parser.add_argument("--md-out", type=Path, default=Path("paper-semantic-baselines.md"))
    args = parser.parse_args()

    manifest = load_manifest()
    verify_router_frozen(manifest)
    tasks = load_tasks(args.dataset_root, manifest)
    frozen_payload = evaluate_frozen(tasks, manifest)
    frozen_rows = frozen_payload["rows"]
    frozen_correct = [bool(r["correct"]) for r in frozen_rows]
    frozen_low, frozen_high = wilson_interval(sum(frozen_correct), len(frozen_correct))

    task_text = {t["task_id"]: t["text"] for t in tasks}
    result = {
        "status": "exploratory-post-hoc-on-previously-frozen-untouched-set",
        "benchmark": manifest["external_benchmark"],
        "frozen_router_commit": manifest["frozen_router_commit"],
        "frozen_router": {
            "hit_at_1": frozen_payload["summary"]["hit_at_1"],
            "wilson_95": [frozen_low, frozen_high],
        },
        "baselines": {},
        "comparisons": {},
        "failure_cases": [],
    }

    for model_name in args.models:
        rows = semantic_predictions(tasks, model_name)
        result["baselines"][model_name] = score(rows)
        semantic_correct = [bool(r["correct"]) for r in rows]
        result["comparisons"][model_name] = {
            "frozen_minus_semantic_bootstrap": paired_bootstrap_difference(
                [float(v) for v in frozen_correct], [float(v) for v in semantic_correct]
            ),
            "mcnemar_exact": exact_mcnemar_pvalue(frozen_correct, semantic_correct),
        }
        by_id = {r["task_id"]: r for r in rows}
        for frozen in frozen_rows:
            semantic = by_id[frozen["task_id"]]
            if (not frozen["correct"]) or frozen["predicted_family"] != semantic["predicted_family"]:
                result["failure_cases"].append({
                    "task_id": frozen["task_id"],
                    "truth": frozen["family"],
                    "text": task_text.get(frozen["task_id"], ""),
                    "frozen_prediction": frozen["predicted_family"],
                    "frozen_correct": frozen["correct"],
                    "semantic_model": model_name,
                    "semantic_prediction": semantic["predicted_family"],
                    "semantic_correct": semantic["correct"],
                })

    args.json_out.write_text(json.dumps(result, indent=2) + "\n")
    lines = [
        "# Paper-quality semantic router comparison",
        "",
        "This comparison is explicitly **exploratory/post-hoc**: General-AgentBench was originally untouched when the frozen router was first evaluated, but these semantic baselines were added afterward.",
        "",
        "| Router | Hit@1 | Wilson 95% CI |",
        "|---|---:|---:|",
        f"| Frozen AgentWeave | {100*result['frozen_router']['hit_at_1']:.1f}% | [{100*frozen_low:.1f}%, {100*frozen_high:.1f}%] |",
    ]
    for model_name, metrics in result["baselines"].items():
        lo, hi = metrics["wilson_95"]
        lines.append(f"| {model_name} | {100*metrics['hit_at_1']:.1f}% | [{100*lo:.1f}%, {100*hi:.1f}%] |")
    lines += ["", "## Paired significance", ""]
    for model_name, comp in result["comparisons"].items():
        boot = comp["frozen_minus_semantic_bootstrap"]
        mc = comp["mcnemar_exact"]
        lines.append(
            f"- vs `{model_name}`: frozen-minus-baseline Δ={100*boot['difference']:+.1f} pp, bootstrap 95% CI [{100*boot['ci_low']:+.1f}, {100*boot['ci_high']:+.1f}] pp; exact McNemar p={mc['p_value']:.6g}."
        )
    lines += [
        "",
        f"Failure/disagreement rows written to JSON: **{len(result['failure_cases'])}**.",
        "",
        "**Boundary:** this is family-routing accuracy, not benchmark-native task completion. No benchmark label or example is used to fit the zero-shot embedding baselines.",
    ]
    args.md_out.write_text("\n".join(lines) + "\n")
    print(args.md_out.read_text())


if __name__ == "__main__":
    main()
