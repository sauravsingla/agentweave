from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from agentweave.requirements import RequirementAnalyzer
from research.router_v2 import FAMILIES, PrototypeFamilyRouterV2
from scripts.untouched_generalization import load_manifest as load_gab_manifest
from scripts.untouched_generalization import load_tasks as load_gab_tasks
from scripts.untouched_generalization import predict_family as legacy_predict_family


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "evaluation" / "router-v2-holdout.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text())


def load_jsonl(path: Path, field: str, limit: int, family: str, source: str) -> list[dict]:
    rows = []
    with path.open() as handle:
        for idx, line in enumerate(handle):
            if len(rows) >= limit:
                break
            payload = json.loads(line)
            text = str(payload[field]).strip()
            if text:
                rows.append({"family": family, "source": source, "task_id": f"{source}:{idx}", "text": text})
    return rows


def load_jsonl_gz(path: Path, field: str, limit: int, family: str, source: str) -> list[dict]:
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for idx, line in enumerate(handle):
            if len(rows) >= limit:
                break
            payload = json.loads(line)
            text = str(payload[field]).strip()
            if text:
                rows.append({"family": family, "source": source, "task_id": f"{source}:{idx}", "text": text})
    return rows


def load_json_array(path: Path, field: str, limit: int, family: str, source: str) -> list[dict]:
    payload = json.loads(path.read_text())
    rows = []
    for idx, item in enumerate(payload):
        if len(rows) >= limit:
            break
        text = str(item[field]).strip()
        if text:
            rows.append({"family": family, "source": source, "task_id": f"{source}:{idx}", "text": text})
    return rows


def load_holdout(protocol: dict, external_root: Path) -> list[dict]:
    rows: list[dict] = []
    for source in protocol["external_holdout"]["sources"]:
        repo_dir = {
            "openai/grade-school-math": "grade-school-math",
            "openai/human-eval": "human-eval",
            "princeton-nlp/intercode": "intercode",
        }[source["repository"]]
        path = external_root / repo_dir / source["path"]
        if not path.exists():
            raise FileNotFoundError(path)
        kwargs = {
            "path": path,
            "field": source["text_field"],
            "limit": int(source["tasks"]),
            "family": source["family"],
            "source": source["name"],
        }
        if path.suffix == ".gz":
            loaded = load_jsonl_gz(**kwargs)
        elif path.suffix == ".jsonl":
            loaded = load_jsonl(**kwargs)
        else:
            loaded = load_json_array(**kwargs)
        if len(loaded) != int(source["tasks"]):
            raise RuntimeError(f"Expected {source['tasks']} tasks from {source['name']}, loaded {len(loaded)}")
        rows.extend(loaded)
    return rows


def development_rows(gab_root: Path) -> list[dict]:
    manifest = load_gab_manifest()
    rows = load_gab_tasks(gab_root, manifest)
    return rows


def deterministic_fold(row: dict, folds: int = 5) -> int:
    key = f"{row['family']}::{row['task_id']}".encode()
    return int(hashlib.sha256(key).hexdigest()[:12], 16) % folds


def score_rows(rows: list[dict], predictions: list[dict]) -> dict:
    confusion: dict[str, Counter] = defaultdict(Counter)
    by_family: dict[str, list[bool]] = defaultdict(list)
    by_source: dict[str, list[bool]] = defaultdict(list)
    for row, pred in zip(rows, predictions):
        correct = pred["family"] == row["family"]
        by_family[row["family"]].append(correct)
        by_source[row.get("source", row["family"])].append(correct)
        confusion[row["family"]][pred["family"]] += 1
    accuracy = sum(sum(values) for values in by_family.values()) / len(rows)
    family_acc = {
        family: {"tasks": len(values), "accuracy": sum(values) / len(values)}
        for family, values in sorted(by_family.items())
    }
    macro = mean(item["accuracy"] for item in family_acc.values())
    return {
        "tasks": len(rows),
        "hit_at_1": round(accuracy, 6),
        "macro_accuracy": round(macro, 6),
        "per_family": {k: {"tasks": v["tasks"], "accuracy": round(v["accuracy"], 6)} for k, v in family_acc.items()},
        "per_source": {
            source: {"tasks": len(values), "accuracy": round(sum(values) / len(values), 6)}
            for source, values in sorted(by_source.items())
        },
        "confusion_matrix": {family: dict(counter) for family, counter in confusion.items()},
    }


def cross_validate(development: list[dict]) -> dict:
    fold_rows = []
    all_predictions = []
    all_truth = []
    for fold in range(5):
        train = [row for row in development if deterministic_fold(row) != fold]
        test = [row for row in development if deterministic_fold(row) == fold]
        router = PrototypeFamilyRouterV2().fit([(row["text"], row["family"]) for row in train])
        correct = 0
        for row in test:
            pred = router.predict(row["text"])
            all_predictions.append(pred.family)
            all_truth.append(row["family"])
            correct += int(pred.family == row["family"])
        fold_rows.append({"fold": fold, "train": len(train), "test": len(test), "hit_at_1": round(correct / len(test), 6)})
    overall = sum(int(p == y) for p, y in zip(all_predictions, all_truth)) / len(all_truth)
    return {"tasks": len(all_truth), "hit_at_1": round(overall, 6), "folds": fold_rows}


def evaluate(development: list[dict], holdout: list[dict], protocol: dict) -> dict:
    router = PrototypeFamilyRouterV2().fit([(row["text"], row["family"]) for row in development])
    analyzer = RequirementAnalyzer()

    v2_predictions = []
    legacy_predictions = []
    detail_rows = []
    for row in holdout:
        v2 = router.predict(row["text"])
        legacy_family = legacy_predict_family(analyzer.analyze(row["text"]))
        v2_predictions.append({"family": v2.family, "confidence": v2.confidence})
        legacy_predictions.append({"family": legacy_family})
        detail_rows.append(
            {
                "task_id": row["task_id"],
                "source": row["source"],
                "ground_truth_family": row["family"],
                "router_v2_family": v2.family,
                "router_v2_confidence": round(v2.confidence, 6),
                "legacy_family": legacy_family,
                "router_v2_correct": v2.family == row["family"],
                "legacy_correct": legacy_family == row["family"],
                "router_v2_scores": v2.scores,
            }
        )

    v2_metrics = score_rows(holdout, v2_predictions)
    legacy_metrics = score_rows(holdout, legacy_predictions)
    mean_confidence = mean(item["confidence"] for item in v2_predictions)
    v2_metrics["mean_confidence"] = round(mean_confidence, 6)

    return {
        "protocol": protocol,
        "source_integrity": {
            "router_v2_sha256": sha256(ROOT / protocol["router_source"]),
            "protocol_sha256": sha256(PROTOCOL_PATH),
            "repository_head": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
            ).stdout.strip(),
        },
        "development": {
            "tasks": len(development),
            "five_fold_cv": cross_validate(development),
        },
        "holdout": {
            "router_v2": v2_metrics,
            "legacy_frozen_router": legacy_metrics,
            "absolute_hit_at_1_delta": round(v2_metrics["hit_at_1"] - legacy_metrics["hit_at_1"], 6),
        },
        "rows": detail_rows,
        "evidence_boundary": protocol["evidence_boundary"],
    }


def write_markdown(payload: dict, path: Path) -> None:
    v2 = payload["holdout"]["router_v2"]
    legacy = payload["holdout"]["legacy_frozen_router"]
    delta = payload["holdout"]["absolute_hit_at_1_delta"]
    cv = payload["development"]["five_fold_cv"]
    lines = [
        "# Router V2 external holdout",
        "",
        f"Development: General-AgentBench only ({payload['development']['tasks']} prompts).",
        "Holdout: 24 GSM8K + 24 HumanEval + 24 InterCode NL2Bash tasks; source labels withheld during prediction.",
        "",
        "| Metric | Legacy frozen router | Router V2 |",
        "|---|---:|---:|",
        f"| Holdout family Hit@1 | {legacy['hit_at_1'] * 100:.1f}% | **{v2['hit_at_1'] * 100:.1f}%** |",
        f"| Holdout macro accuracy | {legacy['macro_accuracy'] * 100:.1f}% | **{v2['macro_accuracy'] * 100:.1f}%** |",
        f"| Absolute Hit@1 delta | — | **{delta * 100:+.1f} pp** |",
        f"| Mean Router V2 confidence | — | {v2['mean_confidence']:.3f} |",
        "",
        f"General-AgentBench 5-fold development CV Hit@1: **{cv['hit_at_1'] * 100:.1f}%**.",
        "",
        "## Holdout per-family accuracy",
        "",
        "| Family / external source | Legacy | Router V2 |",
        "|---|---:|---:|",
    ]
    for family, metrics in v2["per_family"].items():
        legacy_acc = legacy["per_family"][family]["accuracy"]
        lines.append(f"| {family} | {legacy_acc * 100:.1f}% | {metrics['accuracy'] * 100:.1f}% |")
    lines += [
        "",
        "## Evidence boundary",
        "",
        payload["evidence_boundary"],
        "",
        "The original 15.6% General-AgentBench untouched result is not replaced or recomputed by this experiment. Router V2 is kept outside `agentweave/`, so the frozen legacy-router proof remains byte-for-byte enforceable for the original scope.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, default=Path("router-v2-holdout-results.json"))
    parser.add_argument("--md-out", type=Path, default=Path("router-v2-holdout-results.md"))
    args = parser.parse_args()

    protocol = load_protocol()
    development = development_rows(args.development_root)
    holdout = load_holdout(protocol, args.external_root)
    payload = evaluate(development, holdout, protocol)
    args.json_out.write_text(json.dumps(payload, indent=2) + "\n")
    write_markdown(payload, args.md_out)
    print(args.md_out.read_text())


if __name__ == "__main__":
    main()
