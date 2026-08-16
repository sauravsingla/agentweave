from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean

from research.router_v6 import WebGoalRouterV6
from research.router_v7 import ResearchIntentRouterV7
from scripts.router_v2_holdout import development_rows, score_rows


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "evaluation" / "router-v7-holdout.json"


def load_protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text())


def load_holdout(protocol: dict, external_root: Path) -> list[dict]:
    source = protocol["external_holdout"]
    rows_by_id: dict[str, dict] = {}
    for filename in source["files"]:
        path = external_root / filename
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open() as handle:
            for idx, line in enumerate(handle):
                item = json.loads(line)
                task = str(item.get("task", "")).strip()
                if not task:
                    continue
                task_id = str(item.get("id", f"{filename}:{idx}"))
                rows_by_id[task_id] = {
                    "task_id": task_id,
                    "source": "AssistantBench",
                    "family": source["family"],
                    "text": task,
                }

    ranked = []
    for row in rows_by_id.values():
        digest = hashlib.sha256(f"{row['task_id']}\n{row['text']}".encode()).hexdigest()
        ranked.append((digest, row))
    ranked.sort(key=lambda item: item[0])
    count = int(source["count"])
    rows = [row for _, row in ranked[:count]]
    if len(rows) != count:
        raise RuntimeError(f"Expected {count} AssistantBench tasks, loaded {len(rows)}")
    return rows


def pred_dict(router, text: str) -> dict:
    pred = router.predict(text)
    return {"family": pred.family, "confidence": pred.confidence, "scores": pred.scores}


def evaluate(development: list[dict], holdout: list[dict], protocol: dict) -> dict:
    train = [(row["text"], row["family"]) for row in development]
    v6 = WebGoalRouterV6().fit(train)
    v7 = ResearchIntentRouterV7().fit(train)
    v6_predictions = [pred_dict(v6, row["text"]) for row in holdout]
    v7_predictions = [pred_dict(v7, row["text"]) for row in holdout]
    v6_score = score_rows(holdout, v6_predictions)
    v7_score = score_rows(holdout, v7_predictions)
    return {
        "protocol": protocol,
        "development_tasks": len(development),
        "holdout_tasks": len(holdout),
        "router_v6": v6_score,
        "router_v7": v7_score,
        "absolute_delta": round(v7_score["hit_at_1"] - v6_score["hit_at_1"], 6),
        "mean_confidence_v6": round(mean(p["confidence"] for p in v6_predictions), 6),
        "mean_confidence_v7": round(mean(p["confidence"] for p in v7_predictions), 6),
        "rows": [
            {
                "task_id": row["task_id"],
                "text": row["text"],
                "truth": row["family"],
                "v6": pred6,
                "v7": pred7,
            }
            for row, pred6, pred7 in zip(holdout, v6_predictions, v7_predictions)
        ],
    }


def markdown(result: dict) -> str:
    v6 = result["router_v6"]["hit_at_1"]
    v7 = result["router_v7"]["hit_at_1"]
    delta = result["absolute_delta"]
    return "\n".join(
        [
            "# Router V7 AssistantBench external holdout",
            "",
            f"Development: General-AgentBench published prompts only ({result['development_tasks']} prompts).",
            f"Holdout: {result['holdout_tasks']} untouched AssistantBench information-seeking tasks selected by the preregistered SHA256 rule.",
            "",
            "| Metric | Router V6 | Router V7 |",
            "|---|---:|---:|",
            f"| Search-family Hit@1 | {v6:.1%} | **{v7:.1%}** |",
            f"| Absolute V7-V6 delta | — | **{delta:+.1%}** |",
            f"| Mean confidence | {result['mean_confidence_v6']:.3f} | {result['mean_confidence_v7']:.3f} |",
            "",
            "## Evidence boundary",
            "",
            result["protocol"]["evidence_boundary"],
            "",
            "Router V6's WebArena holdout remains unchanged. Router V7 is frozen for this AssistantBench holdout after the first successful scored run.",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--external-root", type=Path, required=True)
    args = parser.parse_args()

    protocol = load_protocol()
    development = development_rows(args.development_root)
    holdout = load_holdout(protocol, args.external_root)
    result = evaluate(development, holdout, protocol)

    Path("router-v7-holdout-results.json").write_text(json.dumps(result, indent=2))
    report = markdown(result)
    Path("router-v7-holdout-results.md").write_text(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
