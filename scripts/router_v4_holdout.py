from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
from pathlib import Path
from statistics import mean

from research.router_v3 import SemanticFamilyRouterV3
from research.router_v4 import HierarchicalFamilyRouterV4
from scripts.router_v2_holdout import development_rows, score_rows


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "evaluation" / "router-v4-holdout.json"
_INTERACTION_WORDS = re.compile(
    r"\b(navigate|open|click|select|choose|create|update|edit|delete|record|form|list|dashboard|"
    r"incident|request|catalog|field|button|menu|filter|sort|application|page|ticket|mark)\b",
    re.I,
)


def load_protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text())


def stable_select(rows: list[dict], count: int, source: str) -> list[dict]:
    ranked = []
    for row in rows:
        digest = hashlib.sha256(f"{source}\n{row['text']}".encode()).hexdigest()
        ranked.append((digest, row))
    ranked.sort(key=lambda item: item[0])
    selected = [row for _, row in ranked[:count]]
    if len(selected) != count:
        raise RuntimeError(f"Expected {count} rows from {source}, found {len(selected)}")
    return selected


def load_cruxeval(root: Path, count: int) -> list[dict]:
    path = root / "cruxeval" / "data" / "cruxeval.jsonl"
    rows = []
    with path.open() as handle:
        for line in handle:
            item = json.loads(line)
            code = str(item.get("code", "")).strip()
            inp = str(item.get("input", "")).strip()
            if not code:
                continue
            text = f"Determine the output of this Python program for the given input.\n{code}\nInput: {inp}"
            rows.append({"task_id": str(item.get("id", len(rows))), "source": "CRUXEval", "family": "swebench", "text": text})
    return stable_select(rows, count, "CRUXEval")


def _render_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append("{value}")
        return "".join(parts)
    return None


def _target_mentions_goal(target: ast.AST) -> bool:
    if isinstance(target, ast.Name):
        return "goal" in target.id.lower()
    if isinstance(target, ast.Attribute):
        return "goal" in target.attr.lower()
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_target_mentions_goal(item) for item in target.elts)
    return False


def load_workarena(root: Path, count: int) -> list[dict]:
    task_root = root / "workarena" / "src" / "browsergym" / "workarena" / "tasks"
    candidates: dict[str, dict] = {}
    for path in sorted(task_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            texts: list[str] = []
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(_target_mentions_goal(target) for target in targets):
                    rendered = _render_string(node.value)
                    if rendered:
                        texts.append(rendered)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "goal" in node.name.lower():
                for child in ast.walk(node):
                    if isinstance(child, ast.Return) and child.value is not None:
                        rendered = _render_string(child.value)
                        if rendered:
                            texts.append(rendered)
                    elif isinstance(child, (ast.Constant, ast.JoinedStr)):
                        rendered = _render_string(child)
                        if rendered:
                            texts.append(rendered)
            for text in texts:
                cleaned = " ".join(text.split())
                if not (24 <= len(cleaned) <= 500):
                    continue
                if not _INTERACTION_WORDS.search(cleaned):
                    continue
                key = hashlib.sha256(cleaned.encode()).hexdigest()
                candidates[key] = {
                    "task_id": f"{path.relative_to(task_root)}:{key[:10]}",
                    "source": "WorkArena",
                    "family": "terminalbench",
                    "text": cleaned,
                }

    # Some WorkArena goals are assembled from generic task descriptions rather
    # than a variable literally named goal. Include interaction-oriented string
    # constants from task modules as a deterministic fallback.
    if len(candidates) < count:
        for path in sorted(task_root.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                rendered = _render_string(node)
                if not rendered:
                    continue
                cleaned = " ".join(rendered.split())
                if not (32 <= len(cleaned) <= 260) or not _INTERACTION_WORDS.search(cleaned):
                    continue
                if any(token in cleaned for token in ("document.querySelector", "function(", "return ", "import ")):
                    continue
                key = hashlib.sha256(cleaned.encode()).hexdigest()
                candidates.setdefault(
                    key,
                    {
                        "task_id": f"{path.relative_to(task_root)}:{key[:10]}",
                        "source": "WorkArena",
                        "family": "terminalbench",
                        "text": cleaned,
                    },
                )
    return stable_select(list(candidates.values()), count, "WorkArena")


def load_miniwob(root: Path, count: int) -> list[dict]:
    path = root / "browsergym" / "browsergym" / "experiments" / "src" / "browsergym" / "experiments" / "benchmark" / "metadata" / "miniwob.csv"
    rows = []
    with path.open(newline="") as handle:
        for item in csv.DictReader(handle):
            if item.get("browsergym_split") != "test":
                continue
            raw = str(item.get("task_name", "")).strip()
            if not raw:
                continue
            name = raw.removeprefix("miniwob.").replace("-", " ")
            rows.append({
                "task_id": raw,
                "source": "BrowserGym MiniWoB",
                "family": "terminalbench",
                "text": f"Complete this interactive browser task: {name}.",
            })
    return stable_select(rows, count, "BrowserGym MiniWoB")


def load_holdout(protocol: dict, external_root: Path) -> list[dict]:
    counts = {item["name"]: int(item["count"]) for item in protocol["external_holdout"]}
    return (
        load_cruxeval(external_root, counts["CRUXEval"])
        + load_workarena(external_root, counts["WorkArena"])
        + load_miniwob(external_root, counts["BrowserGym MiniWoB"])
    )


def evaluate(development: list[dict], holdout: list[dict], protocol: dict) -> dict:
    training = [(row["text"], row["family"]) for row in development]
    v3 = SemanticFamilyRouterV3().fit(training)
    v4 = HierarchicalFamilyRouterV4().fit(training)
    v3_predictions = []
    v4_predictions = []
    details = []
    for row in holdout:
        p3 = v3.predict(row["text"])
        p4 = v4.predict(row["text"])
        v3_predictions.append({"family": p3.family, "confidence": p3.confidence})
        v4_predictions.append({"family": p4.family, "confidence": p4.confidence})
        details.append({
            "task_id": row["task_id"],
            "source": row["source"],
            "ground_truth_family": row["family"],
            "router_v3_family": p3.family,
            "router_v4_family": p4.family,
            "router_v3_confidence": round(p3.confidence, 6),
            "router_v4_confidence": round(p4.confidence, 6),
            "router_v3_correct": p3.family == row["family"],
            "router_v4_correct": p4.family == row["family"],
        })
    m3 = score_rows(holdout, v3_predictions)
    m4 = score_rows(holdout, v4_predictions)
    m3["mean_confidence"] = round(mean(x["confidence"] for x in v3_predictions), 6)
    m4["mean_confidence"] = round(mean(x["confidence"] for x in v4_predictions), 6)
    return {
        "protocol": protocol,
        "development_tasks": len(development),
        "holdout": {
            "router_v3": m3,
            "router_v4": m4,
            "absolute_hit_at_1_delta": round(m4["hit_at_1"] - m3["hit_at_1"], 6),
        },
        "rows": details,
        "evidence_boundary": protocol["evidence_boundary"],
    }


def write_markdown(payload: dict, path: Path) -> None:
    m3 = payload["holdout"]["router_v3"]
    m4 = payload["holdout"]["router_v4"]
    delta = payload["holdout"]["absolute_hit_at_1_delta"]
    lines = [
        "# Router V4 new external holdout",
        "",
        f"Development: General-AgentBench published prompts only ({payload['development_tasks']} prompts).",
        "Holdout: 24 CRUXEval + 24 WorkArena + 24 BrowserGym MiniWoB items selected by the preregistered SHA256 rule.",
        "",
        "| Metric | Router V3 | Router V4 |",
        "|---|---:|---:|",
        f"| Holdout family Hit@1 | {m3['hit_at_1'] * 100:.1f}% | **{m4['hit_at_1'] * 100:.1f}%** |",
        f"| Macro accuracy | {m3['macro_accuracy'] * 100:.1f}% | **{m4['macro_accuracy'] * 100:.1f}%** |",
        f"| Absolute V4-V3 delta | — | **{delta * 100:+.1f} pp** |",
        f"| Mean confidence | {m3['mean_confidence']:.3f} | {m4['mean_confidence']:.3f} |",
        "",
        "## Per-source accuracy",
        "",
        "| Source | Router V3 | Router V4 |",
        "|---|---:|---:|",
    ]
    for source, metrics in m4["per_source"].items():
        lines.append(f"| {source} | {m3['per_source'][source]['accuracy'] * 100:.1f}% | {metrics['accuracy'] * 100:.1f}% |")
    lines += [
        "",
        "## Evidence boundary",
        "",
        payload["evidence_boundary"],
        "",
        "The original 15.6% frozen-router result, Router V2 holdout, and Router V3 holdout remain unchanged. Router V4 is frozen for this holdout after the first successful scored run.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, default=Path("router-v4-holdout-results.json"))
    parser.add_argument("--md-out", type=Path, default=Path("router-v4-holdout-results.md"))
    args = parser.parse_args()
    protocol = load_protocol()
    development = development_rows(args.development_root)
    holdout = load_holdout(protocol, args.external_root)
    payload = evaluate(development, holdout, protocol)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    write_markdown(payload, args.md_out)
    print(args.md_out.read_text())


if __name__ == "__main__":
    main()
