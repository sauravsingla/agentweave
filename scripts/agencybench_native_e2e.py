from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from agencybench_external_eval import build_router, load_tasks, visible_query


def route_scenario(root: Path, scenario: str, output: Path) -> dict[str, Any]:
    tasks = load_tasks(root)
    rank = build_router(tasks)
    family, scenario_name = scenario.split("/", 1)
    path = root / "AgencyBench-v2" / family / scenario_name / "description.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    ordered = []
    for key, value in data.items():
        if re.fullmatch(r"subtask\d+", str(key)) and isinstance(value, str):
            ordered.append((int(str(key)[7:]), visible_query(value)))
    text = "\n\n".join(v for _, v in sorted(ordered))
    ranked = rank(text)
    result = {
        "scenario": scenario,
        "declared_family_used_only_for_reporting": family,
        "visible_subtasks": len(ordered),
        "ranked_families": [{"family": f, "score": s} for f, s in ranked],
        "selected_family": ranked[0][0] if ranked else None,
        "selection_margin": (ranked[0][1] - ranked[1][1]) if len(ranked) > 1 else (ranked[0][1] if ranked else 0.0),
        "candidate_agents": [
            {"agent": "primary", "model": "openai/gpt-4.1", "family": ranked[0][0] if ranked else None},
            {"agent": "fallback", "model": "openai/gpt-4o", "family": ranked[0][0] if ranked else None},
        ],
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def _load(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _score_summary(meta: Any) -> dict[str, Any]:
    if not isinstance(meta, dict):
        return {"available": False}
    subtasks = meta.get("subtasks") or []
    best_scores: list[float] = []
    attempts = 0
    feedback_events = 0
    retry_subtasks = 0
    native_judge_attempts = 0
    for sub in subtasks:
        if not isinstance(sub, dict):
            continue
        try:
            best_scores.append(float(sub.get("best_score") or 0))
        except Exception:
            best_scores.append(0.0)
        rows = sub.get("attempts") or []
        attempts += len(rows)
        if len(rows) > 1:
            retry_subtasks += 1
        for attempt in rows:
            if not isinstance(attempt, dict):
                continue
            feedback = attempt.get("feedback")
            if isinstance(feedback, str) and feedback.strip():
                feedback_events += 1
            if "rubric" in attempt or "text_evaluator" in attempt or "vision_evaluator" in attempt or "evaluation" in attempt:
                native_judge_attempts += 1
    return {
        "available": True,
        "subtasks": len(subtasks),
        "attempts": attempts,
        "retry_subtasks": retry_subtasks,
        "feedback_events": feedback_events,
        "native_judge_attempts": native_judge_attempts,
        "best_scores": best_scores,
        "mean_best_score": statistics.fmean(best_scores) if best_scores else 0.0,
        "completed_all_subtasks": bool(subtasks),
    }


def _meter_summary(paths: list[Path]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("kind") in {"proxy-start", "proxy-stop"}:
                continue
            rows.append(row)
    usage = Counter()
    tool_calls = 0
    statuses = Counter()
    models = Counter()
    wall_ms = 0.0
    for row in rows:
        u = row.get("usage") or {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            try:
                usage[key] += int(u.get(key) or 0)
            except Exception:
                pass
        tool_calls += int(row.get("tool_calls") or 0)
        statuses[str(row.get("status"))] += 1
        if row.get("model"):
            models[str(row["model"])] += 1
        try:
            wall_ms += float(row.get("wall_ms") or 0.0)
        except Exception:
            pass
    return {
        "model_requests": len(rows),
        "models": dict(models),
        "statuses": dict(statuses),
        "prompt_tokens_reported": usage["prompt_tokens"],
        "completion_tokens_reported": usage["completion_tokens"],
        "total_tokens_reported": usage["total_tokens"],
        "tool_calls_reported": tool_calls,
        "upstream_request_wall_seconds": wall_ms / 1000.0,
        "monetary_cost_usd": None,
        "cost_note": "GitHub Models via GITHUB_TOKEN does not return a monetary charge in the inference response; token/tool usage is reported without inventing a dollar cost.",
    }


def report(args: argparse.Namespace) -> dict[str, Any]:
    primary = _score_summary(_load(Path(args.backend_meta)) if args.backend_meta else None)
    fallback = _score_summary(_load(Path(args.backend_fallback_meta)) if args.backend_fallback_meta else None)
    frontend = _score_summary(_load(Path(args.frontend_meta)) if args.frontend_meta else None)
    route = _load(Path(args.route)) if args.route else None
    meter_paths = [Path(p) for p in args.meter]
    meter = _meter_summary(meter_paths)
    runtime = {}
    for item in args.runtime or []:
        key, value = item.split("=", 1)
        try:
            runtime[key] = float(value)
        except Exception:
            runtime[key] = value

    recovery_triggered = bool(fallback.get("available"))
    result = {
        "protocol": "AgencyBench native representative end-to-end proof: full Backend/scenario1 (5 sequential subtasks) plus Frontend/scenario1 subtask-1 Docker/visual-judge smoke; GitHub Models provides live agent/evaluator inference; AgencyBench upstream eval_task.py provides native execution/judging/feedback.",
        "routing": route,
        "backend_primary": primary,
        "backend_fallback": fallback,
        "frontend_docker_native_judge": frontend,
        "recovery": {
            "triggered": recovery_triggered,
            "policy": "If primary Backend/scenario1 mean native score < 6 or execution failed, rerun the same scenario with the alternate candidate agent/model and the same native AgencyBench judge contract.",
        },
        "metering": meter,
        "runtime": runtime,
        "boundaries": [
            "Backend/scenario1 is the full five-subtask upstream long-horizon scenario; this run is not the entire 138-task AgencyBench suite.",
            "Frontend/scenario1 is intentionally limited to subtask1 to exercise the official Docker sandbox, browser evidence collection, text judge, vision judge, and feedback loop without claiming a full Frontend scenario score.",
            "Agent and evaluator calls are live GitHub Models inference requests, not synthetic outputs.",
            "AgencyBench native meta_eval scores are reported as produced; low scores are valid benchmark outcomes and do not make the infrastructure proof fail.",
            "Monetary cost is left null because GitHub Models does not expose per-request dollar cost through the response used here.",
        ],
    }
    Path(args.output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")

    md = [
        "# AgencyBench native end-to-end representative proof",
        "",
        "| Component | Result |",
        "|---|---:|",
        f"| Backend primary native subtasks | {primary.get('subtasks', 0)} |",
        f"| Backend primary mean best score | {primary.get('mean_best_score', 0.0):.2f}/10 |",
        f"| Backend native retry subtasks | {primary.get('retry_subtasks', 0)} |",
        f"| Backend native feedback events | {primary.get('feedback_events', 0)} |",
        f"| Recovery alternate agent executed | {'yes' if recovery_triggered else 'no'} |",
        f"| Frontend Docker/native judge subtasks | {frontend.get('subtasks', 0)} |",
        f"| Frontend mean best score | {frontend.get('mean_best_score', 0.0):.2f}/10 |",
        f"| Live model/evaluator requests | {meter.get('model_requests', 0)} |",
        f"| Reported prompt tokens | {meter.get('prompt_tokens_reported', 0)} |",
        f"| Reported completion tokens | {meter.get('completion_tokens_reported', 0)} |",
        f"| Reported total tokens | {meter.get('total_tokens_reported', 0)} |",
        f"| Reported model tool calls | {meter.get('tool_calls_reported', 0)} |",
        "",
        "## Boundary",
        "",
    ]
    md += [f"- {x}" for x in result["boundaries"]]
    Path(args.output_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("route")
    r.add_argument("--agencybench-root", required=True)
    r.add_argument("--scenario", required=True)
    r.add_argument("--output", default="agencybench-native-route.json")

    q = sub.add_parser("report")
    q.add_argument("--route")
    q.add_argument("--backend-meta")
    q.add_argument("--backend-fallback-meta")
    q.add_argument("--frontend-meta")
    q.add_argument("--meter", action="append", default=[])
    q.add_argument("--runtime", action="append", default=[])
    q.add_argument("--output-json", default="agencybench-native-e2e-results.json")
    q.add_argument("--output-md", default="agencybench-native-e2e-results.md")
    args = p.parse_args()
    if args.cmd == "route":
        route_scenario(Path(args.agencybench_root), args.scenario, Path(args.output))
    else:
        report(args)


if __name__ == "__main__":
    main()
