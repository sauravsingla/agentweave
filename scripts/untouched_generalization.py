from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from agentweave.requirements import RequirementAnalyzer


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "evaluation" / "untouched-generalization.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def verify_router_frozen(manifest: dict) -> None:
    frozen = manifest["frozen_router_commit"]
    subprocess.run(["git", "cat-file", "-e", f"{frozen}^{{commit}}"], cwd=ROOT, check=True)
    changed = subprocess.run(
        ["git", "diff", "--name-only", frozen, "HEAD", "--", manifest["frozen_scope"]],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if changed:
        raise RuntimeError(
            "Untouched-generalization protocol violated: frozen AgentWeave code changed:\n" + changed
        )


def first_user_text(payload: dict) -> str | None:
    trace = payload.get("trace") or {}
    for message in trace.get("messages") or []:
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            text = message["content"].strip()
            if text:
                return text
    return None


def load_tasks(dataset_root: Path, manifest: dict) -> list[dict]:
    tasks: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for expected_family, dirname in manifest["canonical_trace_directories"].items():
        trace_dir = dataset_root / dirname / "traces"
        if not trace_dir.exists():
            raise FileNotFoundError(f"Missing preregistered trace directory: {trace_dir}")
        for path in sorted(trace_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            benchmark = str(payload.get("benchmark") or "").lower()
            task_id = str(payload.get("task_id") or (payload.get("trace") or {}).get("task_id") or path.stem)
            text = first_user_text(payload)
            if not text:
                continue
            # The published benchmark field is ground truth only; prediction never receives it.
            if benchmark and benchmark != expected_family:
                raise RuntimeError(
                    f"Preregistered directory {dirname} contained unexpected benchmark={benchmark!r}"
                )
            key = (expected_family, task_id)
            if key in seen:
                continue
            seen.add(key)
            tasks.append(
                {
                    "family": expected_family,
                    "task_id": task_id,
                    "text": text,
                    "source_file": str(path.relative_to(dataset_root)),
                }
            )
    if not tasks:
        raise RuntimeError("No General-AgentBench tasks were loaded")
    return tasks


def predict_family(requirement) -> str:
    caps = {str(v).lower() for v in requirement.capabilities}
    domains = {str(v).lower() for v in requirement.domains}
    if caps & {"mcp", "tool-use", "integration"}:
        return "mcpbench"
    if caps & {"operating-system", "shell"}:
        return "terminalbench"
    if "compliance" in caps or "compliance" in domains:
        return "tau2bench"
    if caps & {"coding", "backend", "frontend", "database", "sql"}:
        return "swebench"
    if caps & {"research", "retrieval", "knowledge-graph"}:
        return "search"
    return "mathhay"


def evaluate(tasks: list[dict], manifest: dict) -> dict:
    analyzer = RequirementAnalyzer()
    rows: list[dict] = []
    confusion: dict[str, Counter] = defaultdict(Counter)
    by_family: dict[str, list[bool]] = defaultdict(list)

    for task in tasks:
        requirement = analyzer.analyze(task["text"])
        predicted = predict_family(requirement)
        correct = predicted == task["family"]
        confusion[task["family"]][predicted] += 1
        by_family[task["family"]].append(correct)
        rows.append(
            {
                "family": task["family"],
                "task_id": task["task_id"],
                "predicted_family": predicted,
                "correct": correct,
                "inference_confidence": round(float(requirement.inference_confidence), 4),
                "inference_source": requirement.inference_source,
                "capabilities": sorted(requirement.capabilities),
                "domains": sorted(requirement.domains),
                "source_file": task["source_file"],
            }
        )

    family_metrics = {}
    for family in manifest["canonical_trace_directories"]:
        values = by_family[family]
        family_metrics[family] = {
            "tasks": len(values),
            "accuracy": round(sum(values) / len(values), 6) if values else None,
        }

    accuracies = [v["accuracy"] for v in family_metrics.values() if v["accuracy"] is not None]
    family_counts = Counter(row["family"] for row in rows)
    majority = max(family_counts.values()) / len(rows)
    overall = sum(row["correct"] for row in rows) / len(rows)

    return {
        "protocol": {
            "frozen_router_commit": manifest["frozen_router_commit"],
            "external_benchmark": manifest["external_benchmark"],
            "anti_tuning_rule": manifest["anti_tuning_rule"],
        },
        "summary": {
            "tasks": len(rows),
            "families": len(family_metrics),
            "hit_at_1": round(overall, 6),
            "macro_accuracy": round(mean(accuracies), 6),
            "majority_baseline": round(majority, 6),
            "mean_inference_confidence": round(mean(row["inference_confidence"] for row in rows), 6),
        },
        "per_family": family_metrics,
        "confusion_matrix": {family: dict(counter) for family, counter in confusion.items()},
        "rows": rows,
        "evidence_boundary": manifest["evidence_boundary"],
    }


def write_markdown(payload: dict, path: Path) -> None:
    summary = payload["summary"]
    lines = [
        "# Untouched benchmark generalization — General-AgentBench",
        "",
        f"Frozen AgentWeave router commit: `{payload['protocol']['frozen_router_commit']}`",
        f"Pinned external benchmark commit: `{payload['protocol']['external_benchmark']['commit']}`",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Tasks | {summary['tasks']} |",
        f"| Families | {summary['families']} |",
        f"| Family Hit@1 | **{summary['hit_at_1'] * 100:.1f}%** |",
        f"| Macro family accuracy | **{summary['macro_accuracy'] * 100:.1f}%** |",
        f"| Majority baseline | {summary['majority_baseline'] * 100:.1f}% |",
        f"| Mean analyzer confidence | {summary['mean_inference_confidence']:.3f} |",
        "",
        "## Per-family accuracy",
        "",
        "| Family | Tasks | Accuracy |",
        "|---|---:|---:|",
    ]
    for family, metrics in payload["per_family"].items():
        acc = metrics["accuracy"]
        lines.append(f"| {family} | {metrics['tasks']} | {acc * 100:.1f}% |")
    lines += [
        "",
        "## Protocol boundary",
        "",
        payload["evidence_boundary"],
        "",
        "The benchmark label is withheld until after `RequirementAnalyzer.analyze()` and the preregistered family rule produce a prediction. The workflow fails if `agentweave/` differs from the frozen router commit.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, default=Path("untouched-generalization-results.json"))
    parser.add_argument("--md-out", type=Path, default=Path("untouched-generalization-results.md"))
    args = parser.parse_args()

    manifest = load_manifest()
    verify_router_frozen(manifest)
    tasks = load_tasks(args.dataset_root, manifest)
    payload = evaluate(tasks, manifest)
    args.json_out.write_text(json.dumps(payload, indent=2) + "\n")
    write_markdown(payload, args.md_out)
    print(args.md_out.read_text())


if __name__ == "__main__":
    main()
