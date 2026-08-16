from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean

from research.router_v5 import InteractiveIntentRouterV5
from research.router_v6 import WebGoalRouterV6
from scripts.router_v2_holdout import development_rows, score_rows


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "evaluation" / "router-v6-holdout.json"


def load_protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text())


def load_holdout(protocol: dict, external_root: Path) -> list[dict]:
    source = protocol["external_holdout"]
    path = external_root / "visualwebarena" / source["path"]
    payload = json.loads(path.read_text())
    ranked = []
    for idx, item in enumerate(payload):
        intent = str(item.get("intent", "")).strip()
        if not intent:
            continue
        task_id = str(item.get("task_id", idx))
        row = {
            "task_id": task_id,
            "source": "WebArena",
            "family": source["family"],
            "text": intent,
        }
        digest = hashlib.sha256(f"{task_id}\n{intent}".encode()).hexdigest()
        ranked.append((digest, row))
    ranked.sort(key=lambda item: item[0])
    count = int(source["count"])
    rows = [row for _, row in ranked[:count]]
    if len(rows) != count:
        raise RuntimeError(f"Expected {count} WebArena tasks, loaded {len(rows)}")
    return rows


def pred_dict(router, text: str) -> dict:
    pred = router.predict(text)
    return {"family": pred.family, "confidence": pred.confidence, "scores": pred.scores}


def evaluate(development: list[dict], holdout: list[dict], protocol: dict) -> dict:
    train = [(row["text"], row["family"]) for row in development]
    v5 = InteractiveIntentRouterV5().fit(train)
    v6 = WebGoalRouterV6().fit(train)
    v5_predictions = [pred_dict(v5, row["text"]) for row in holdout]
    v6_predictions = [pred_dict(v6, row["text"]) for row in holdout]
    v5_score = score_rows(holdout, v5_predictions)
    v6_score = score_rows(holdout, v6_predictions)
    return {
        "protocol": protocol,
        "development_tasks": len(development),
        "holdout_tasks": len(holdout),
        "router_v5": v5_score,
        "router_v6": v6_score,
        "absolute_delta": round(v6_score["hit_at_1"] - v5_score["hit_at_1"], 6),
        "mean_confidence_v5": round(mean(p["confidence"] for p in v5_predictions), 6),
        "mean_confidence_v6": round(mean(p["confidence"] for p in v6_predictions), 6),
        "rows": [
            {
                "task_id": row["task_id"],
                "text": row["text"],
                "truth": row["family"],
                "v5": pred5,
                "v6": pred6,
            }
            for row, pred5, pred6 in zip(holdout, v5_predictions, v6_predictions)
        ],
    }


def markdown(result: dict) -> str:
    v5 = result["router_v5"]["hit_at_1"]
    v6 = result["router_v6"]["hit_at_1"]
    delta = result["absolute_delta"]
    return f"""# Router V6 WebArena external holdout

Development: General-AgentBench published prompts only ({result['development_tasks']} prompts).
Holdout: {result['holdout_tasks']} untouched WebArena natural-language tasks selected by the preregistered SHA256 rule.

| Metric | Router V5 | Router V6 |
|---|---:|---:|
| Interactive-family Hit@1 | {v5*100:.1f}% | **{v6*100:.1f}%** |
| Absolute V6-V5 delta | — | **{delta*100:+.1f} pp** |
| Mean confidence | {result['mean_confidence_v5']:.3f} | {result['mean_confidence_v6']:.3f} |

## Evidence boundary

This is task-family routing transfer only. It does not claim native WebArena environment success, browser action correctness, or end-to-end task completion.

Router V5's VisualWebArena holdout remains unchanged. Router V6 is frozen for this WebArena holdout after the first successful scored run.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--external-root", type=Path, required=True)
    args = parser.parse_args()
    protocol = load_protocol()
    dev = development_rows(args.development_root)
    holdout = load_holdout(protocol, args.external_root)
    result = evaluate(dev, holdout, protocol)
    ROOT.joinpath("router-v6-holdout-results.json").write_text(json.dumps(result, indent=2))
    report = markdown(result)
    ROOT.joinpath("router-v6-holdout-results.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
