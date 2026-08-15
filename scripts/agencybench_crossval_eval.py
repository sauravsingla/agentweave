from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from agencybench_external_eval import FAMILIES, build_dev_trained_router, load_tasks

FOLDS = 5
SEED_PREFIX = "agentweave-agencybench-groupcv-v1:"


def assign_folds(tasks: list[dict]) -> dict[str, int]:
    scenarios_by_family: dict[str, list[str]] = defaultdict(list)
    seen = set()
    for task in tasks:
        key = task["scenario"]
        if key not in seen:
            scenarios_by_family[task["family"]].append(key)
            seen.add(key)

    assignment: dict[str, int] = {}
    for family in FAMILIES:
        names = sorted(
            scenarios_by_family[family],
            key=lambda name: hashlib.sha256((SEED_PREFIX + name).encode()).hexdigest(),
        )
        for index, name in enumerate(names):
            assignment[name] = index % FOLDS
    return assignment


def evaluate(tasks: list[dict]) -> dict:
    assignment = assign_folds(tasks)
    folds = []
    all_rows = []
    total1 = total2 = total3 = 0
    per_family_total = Counter()
    per_family_hit1 = Counter()

    for fold in range(FOLDS):
        train = [t for t in tasks if assignment[t["scenario"]] != fold]
        test = [t for t in tasks if assignment[t["scenario"]] == fold]
        rank = build_dev_trained_router(train)
        hit1 = hit2 = hit3 = 0
        family_counts = Counter()
        family_hits = Counter()

        for task in test:
            ranked = rank(task["query"])
            names = [x[0] for x in ranked]
            ok1 = names[0] == task["family"]
            ok2 = task["family"] in names[:2]
            ok3 = task["family"] in names[:3]
            hit1 += int(ok1)
            hit2 += int(ok2)
            hit3 += int(ok3)
            total1 += int(ok1)
            total2 += int(ok2)
            total3 += int(ok3)
            family_counts[task["family"]] += 1
            family_hits[task["family"]] += int(ok1)
            per_family_total[task["family"]] += 1
            per_family_hit1[task["family"]] += int(ok1)
            all_rows.append({
                "fold": fold,
                "scenario": task["scenario"],
                "task": task["id"],
                "ground_truth": task["family"],
                "prediction": names[0],
                "top3": names[:3],
            })

        folds.append({
            "fold": fold,
            "train_tasks": len(train),
            "test_tasks": len(test),
            "test_scenarios": sorted({t["scenario"] for t in test}),
            "hit1": hit1 / len(test) if test else 0.0,
            "hit2": hit2 / len(test) if test else 0.0,
            "hit3": hit3 / len(test) if test else 0.0,
            "per_family": {
                family: {
                    "tasks": family_counts[family],
                    "hit1": family_hits[family] / family_counts[family] if family_counts[family] else 0.0,
                }
                for family in FAMILIES
            },
        })

    return {
        "protocol": "5-fold scenario-grouped stratified cross-validation; each task is scored only by a family centroid trained on other scenarios; deliverables/rubrics excluded upstream",
        "folds": FOLDS,
        "tasks": len(tasks),
        "scenarios": len(set(assignment)),
        "out_of_fold_hit1": total1 / len(tasks),
        "out_of_fold_hit2": total2 / len(tasks),
        "out_of_fold_hit3": total3 / len(tasks),
        "per_family": {
            family: {
                "tasks": per_family_total[family],
                "hit1": per_family_hit1[family] / per_family_total[family] if per_family_total[family] else 0.0,
            }
            for family in FAMILIES
        },
        "fold_results": folds,
        "rows": all_rows,
    }


def markdown(result: dict) -> str:
    lines = [
        "# AgencyBench scenario-grouped cross-validation",
        "",
        "This is a supervised routing analysis separate from the zero-shot AgentWeave result. It uses **5-fold scenario-grouped stratified cross-validation**: a scenario is never split between train and test, and each task is scored only with family centroids trained on other scenarios.",
        "",
        f"Tasks: **{result['tasks']}** across **{result['scenarios']} scenarios**.",
        "",
        "| Out-of-fold metric | Result |",
        "|---|---:|",
        f"| Hit@1 | **{result['out_of_fold_hit1']:.1%}** |",
        f"| Hit@2 | **{result['out_of_fold_hit2']:.1%}** |",
        f"| Hit@3 | **{result['out_of_fold_hit3']:.1%}** |",
        "",
        "## Per family",
        "",
        "| Family | Tasks | OOF Hit@1 |",
        "|---|---:|---:|",
    ]
    for family in FAMILIES:
        x = result["per_family"][family]
        lines.append(f"| {family} | {x['tasks']} | {x['hit1']:.1%} |")

    lines += [
        "",
        "## Fold results",
        "",
        "| Fold | Test tasks | Hit@1 | Hit@2 | Hit@3 |",
        "|---:|---:|---:|---:|---:|",
    ]
    for fold in result["fold_results"]:
        lines.append(
            f"| {fold['fold']} | {fold['test_tasks']} | {fold['hit1']:.1%} | {fold['hit2']:.1%} | {fold['hit3']:.1%} |"
        )

    lines += [
        "",
        "## Boundary",
        "",
        "- Training labels come only from the other folds; the held-out scenario's family label is used only for scoring.",
        "- Scenario grouping prevents earlier/later subtasks from the same scenario leaking across train/test.",
        "- This is supervised family-routing cross-validation, not zero-shot routing and not AgencyBench end-to-end task completion.",
        "- The cross-validation protocol was added after earlier aggregate benchmark inspection, so it should not be described as preregistered or untouched evaluation.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agencybench-root", default="external/AgencyBench")
    args = parser.parse_args()
    tasks = load_tasks(Path(args.agencybench_root))
    result = evaluate(tasks)
    Path("agencybench-crossval-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    md = markdown(result)
    Path("agencybench-crossval-results.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
