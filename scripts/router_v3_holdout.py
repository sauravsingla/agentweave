from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean

from research.router_v2 import PrototypeFamilyRouterV2
from research.router_v3 import SemanticFamilyRouterV3
from scripts.router_v2_holdout import development_rows, score_rows


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "evaluation" / "router-v3-holdout.json"


def load_protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text())


def stable_select(rows: list[dict], count: int) -> list[dict]:
    ranked = []
    for row in rows:
        key = f"{row['task_id']}\n{row['text']}".encode("utf-8")
        ranked.append((hashlib.sha256(key).hexdigest(), row))
    ranked.sort(key=lambda item: item[0])
    return [row for _, row in ranked[:count]]


def load_mbpp(path: Path, count: int) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for idx, line in enumerate(handle):
            payload = json.loads(line)
            text = str(payload.get("text", "")).strip()
            if text:
                task_id = str(payload.get("task_id", idx))
                rows.append({
                    "family": "swebench",
                    "source": "MBPP",
                    "task_id": f"MBPP:{task_id}",
                    "text": text,
                })
    return stable_select(rows, count)


def load_truthfulqa(path: Path, count: int) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        for idx, payload in enumerate(csv.DictReader(handle)):
            text = str(payload.get("Question", "")).strip()
            if text:
                rows.append({
                    "family": "search",
                    "source": "TruthfulQA",
                    "task_id": f"TruthfulQA:{idx}",
                    "text": text,
                })
    return stable_select(rows, count)


def load_osworld(root: Path, count: int) -> list[dict]:
    rows = []
    for path in sorted(root.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        text = str(payload.get("instruction", "")).strip()
        if text:
            task_id = str(payload.get("id", path.stem))
            rows.append({
                "family": "terminalbench",
                "source": "OSWorld",
                "task_id": f"OSWorld:{task_id}",
                "text": text,
            })
    return stable_select(rows, count)


def load_holdout(protocol: dict, external_root: Path) -> list[dict]:
    specs = {item["name"]: item for item in protocol["external_holdout"]}
    rows = []
    rows.extend(load_mbpp(
        external_root / "google-research" / specs["MBPP"]["path"],
        int(specs["MBPP"]["count"]),
    ))
    rows.extend(load_truthfulqa(
        external_root / "truthfulqa" / specs["TruthfulQA"]["path"],
        int(specs["TruthfulQA"]["count"]),
    ))
    rows.extend(load_osworld(
        external_root / "osworld" / specs["OSWorld"]["path"],
        int(specs["OSWorld"]["count"]),
    ))
    expected = sum(int(item["count"]) for item in protocol["external_holdout"])
    if len(rows) != expected:
        raise RuntimeError(f"Expected {expected} holdout tasks, loaded {len(rows)}")
    return rows


def evaluate(development: list[dict], holdout: list[dict], protocol: dict) -> dict:
    train = [(row["text"], row["family"]) for row in development]
    v2 = PrototypeFamilyRouterV2().fit(train)
    v3 = SemanticFamilyRouterV3().fit(train)

    v2_predictions = []
    v3_predictions = []
    detail_rows = []
    for row in holdout:
        p2 = v2.predict(row["text"])
        p3 = v3.predict(row["text"])
        v2_predictions.append({"family": p2.family, "confidence": p2.confidence})
        v3_predictions.append({"family": p3.family, "confidence": p3.confidence})
        detail_rows.append({
            "task_id": row["task_id"],
            "source": row["source"],
            "ground_truth_family": row["family"],
            "router_v2_family": p2.family,
            "router_v2_confidence": round(p2.confidence, 6),
            "router_v3_family": p3.family,
            "router_v3_confidence": round(p3.confidence, 6),
            "router_v2_correct": p2.family == row["family"],
            "router_v3_correct": p3.family == row["family"],
            "router_v3_scores": p3.scores,
        })

    v2_metrics = score_rows(holdout, v2_predictions)
    v3_metrics = score_rows(holdout, v3_predictions)
    v2_metrics["mean_confidence"] = round(mean(p["confidence"] for p in v2_predictions), 6)
    v3_metrics["mean_confidence"] = round(mean(p["confidence"] for p in v3_predictions), 6)

    return {
        "protocol": protocol,
        "development": {"tasks": len(development)},
        "holdout": {
            "router_v2": v2_metrics,
            "router_v3": v3_metrics,
            "absolute_v3_minus_v2_hit_at_1": round(v3_metrics["hit_at_1"] - v2_metrics["hit_at_1"], 6),
        },
        "rows": detail_rows,
        "evidence_boundary": protocol["evidence_boundary"],
    }


def write_markdown(payload: dict, path: Path) -> None:
    v2 = payload["holdout"]["router_v2"]
    v3 = payload["holdout"]["router_v3"]
    delta = payload["holdout"]["absolute_v3_minus_v2_hit_at_1"]
    lines = [
        "# Router V3 new external holdout",
        "",
        f"Development: General-AgentBench published prompts only ({payload['development']['tasks']} prompts).",
        "Holdout: 24 MBPP + 24 TruthfulQA + 24 OSWorld tasks selected by the preregistered SHA256 rule.",
        "",
        "| Metric | Router V2 | Router V3 |",
        "|---|---:|---:|",
        f"| Holdout family Hit@1 | {v2['hit_at_1'] * 100:.1f}% | **{v3['hit_at_1'] * 100:.1f}%** |",
        f"| Holdout macro accuracy | {v2['macro_accuracy'] * 100:.1f}% | **{v3['macro_accuracy'] * 100:.1f}%** |",
        f"| Absolute V3-V2 delta | — | **{delta * 100:+.1f} pp** |",
        f"| Mean confidence | {v2['mean_confidence']:.3f} | {v3['mean_confidence']:.3f} |",
        "",
        "## Per-family accuracy",
        "",
        "| Family | Router V2 | Router V3 |",
        "|---|---:|---:|",
    ]
    for family, metrics in v3["per_family"].items():
        lines.append(
            f"| {family} | {v2['per_family'][family]['accuracy'] * 100:.1f}% | {metrics['accuracy'] * 100:.1f}% |"
        )
    lines += [
        "",
        "## Evidence boundary",
        "",
        payload["evidence_boundary"],
        "",
        "Router V2's original 72-task holdout and the original 15.6% untouched General-AgentBench result remain frozen and are not used as V3 scoring data.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, default=Path("router-v3-holdout-results.json"))
    parser.add_argument("--md-out", type=Path, default=Path("router-v3-holdout-results.md"))
    args = parser.parse_args()

    protocol = load_protocol()
    development = development_rows(args.development_root)
    holdout = load_holdout(protocol, args.external_root)
    payload = evaluate(development, holdout, protocol)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload, args.md_out)
    print(args.md_out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
