from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean

from research.router_v4 import HierarchicalFamilyRouterV4
from research.router_v5 import InteractiveIntentRouterV5
from scripts.router_v2_holdout import development_rows, score_rows


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "evaluation" / "router-v5-holdout.json"


def load_protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text())


def stable_select(rows: list[dict], count: int, domain: str) -> list[dict]:
    ranked = []
    for row in rows:
        digest = hashlib.sha256(
            f"{domain}\n{row['task_id']}\n{row['text']}".encode()
        ).hexdigest()
        ranked.append((digest, row))
    ranked.sort(key=lambda item: item[0])
    selected = [row for _, row in ranked[:count]]
    if len(selected) != count:
        raise RuntimeError(f"Expected {count} rows from {domain}, found {len(selected)}")
    return selected


def load_domain(path: Path, domain: str, count: int) -> list[dict]:
    payload = json.loads(path.read_text())
    rows = []
    for idx, item in enumerate(payload):
        intent = str(item.get("intent", "")).strip()
        if not intent:
            continue
        rows.append(
            {
                "task_id": str(item.get("task_id", idx)),
                "source": f"VisualWebArena/{domain}",
                "domain": domain,
                "family": "terminalbench",
                "text": intent,
            }
        )
    return stable_select(rows, count, domain)


def load_holdout(protocol: dict, external_root: Path) -> list[dict]:
    source = protocol["external_holdout"]
    rows: list[dict] = []
    repo_root = external_root / "visualwebarena"
    for domain in source["domains"]:
        path = repo_root / domain["path"]
        if not path.exists():
            raise FileNotFoundError(path)
        rows.extend(load_domain(path, domain["name"], int(domain["count"])))
    return rows


def prediction_dict(router, text: str) -> dict:
    pred = router.predict(text)
    return {
        "family": pred.family,
        "confidence": pred.confidence,
        "scores": pred.scores,
    }


def evaluate(development: list[dict], holdout: list[dict], protocol: dict) -> dict:
    train = [(row["text"], row["family"]) for row in development]
    v4 = HierarchicalFamilyRouterV4().fit(train)
    v5 = InteractiveIntentRouterV5().fit(train)

    v4_predictions = [prediction_dict(v4, row["text"]) for row in holdout]
    v5_predictions = [prediction_dict(v5, row["text"]) for row in holdout]
    v4_score = score_rows(holdout, v4_predictions)
    v5_score = score_rows(holdout, v5_predictions)

    v4_conf = mean(item["confidence"] for item in v4_predictions)
    v5_conf = mean(item["confidence"] for item in v5_predictions)

    return {
        "protocol": protocol,
        "development_tasks": len(development),
        "holdout_tasks": len(holdout),
        "router_v4": {**v4_score, "mean_confidence": round(v4_conf, 6)},
        "router_v5": {**v5_score, "mean_confidence": round(v5_conf, 6)},
        "absolute_delta_pp": round((v5_score["hit_at_1"] - v4_score["hit_at_1"]) * 100, 1),
        "rows": [
            {
                "task_id": row["task_id"],
                "source": row["source"],
                "text": row["text"],
                "truth": row["family"],
                "router_v4": v4_pred,
                "router_v5": v5_pred,
            }
            for row, v4_pred, v5_pred in zip(holdout, v4_predictions, v5_predictions)
        ],
    }


def render_markdown(result: dict) -> str:
    v4 = result["router_v4"]
    v5 = result["router_v5"]
    lines = [
        "# Router V5 interactive external holdout",
        "",
        f"Development: General-AgentBench published prompts only ({result['development_tasks']} prompts).",
        f"Holdout: {result['holdout_tasks']} VisualWebArena tasks across classifieds, Reddit, and shopping, selected by the preregistered SHA256 rule.",
        "",
        "| Metric | Router V4 | Router V5 |",
        "|---|---:|---:|",
        f"| Interactive-family Hit@1 | {v4['hit_at_1']*100:.1f}% | **{v5['hit_at_1']*100:.1f}%** |",
        f"| Absolute V5-V4 delta | — | **{result['absolute_delta_pp']:+.1f} pp** |",
        f"| Mean confidence | {v4['mean_confidence']:.3f} | {v5['mean_confidence']:.3f} |",
        "",
        "## Per-domain accuracy",
        "",
        "| Domain | Router V4 | Router V5 |",
        "|---|---:|---:|",
    ]
    for domain in ["classifieds", "reddit", "shopping"]:
        source = f"VisualWebArena/{domain}"
        v4_acc = v4["per_source"][source]["accuracy"]
        v5_acc = v5["per_source"][source]["accuracy"]
        lines.append(f"| {domain} | {v4_acc*100:.1f}% | {v5_acc*100:.1f}% |")
    lines += [
        "",
        "## Evidence boundary",
        "",
        "This is interactive task-family routing transfer only. It does not claim native VisualWebArena environment success, action execution correctness, or visual grounding performance.",
        "",
        "The original frozen-router result and Router V2/V3/V4 holdouts remain unchanged. Router V5 is frozen for this holdout after the first successful scored run.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--external-root", type=Path, required=True)
    args = parser.parse_args()

    protocol = load_protocol()
    development = development_rows(args.development_root)
    holdout = load_holdout(protocol, args.external_root)
    result = evaluate(development, holdout, protocol)

    (ROOT / "router-v5-holdout-results.json").write_text(json.dumps(result, indent=2))
    markdown = render_markdown(result)
    (ROOT / "router-v5-holdout-results.md").write_text(markdown)
    print(markdown)


if __name__ == "__main__":
    main()
