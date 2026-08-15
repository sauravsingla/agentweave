from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from agencybench_external_eval import build_router, load_tasks, visible_query

PRIMARY_MODEL = "llama3.2:3b"
FALLBACK_MODEL = "granite3.3:2b"
VISION_MODEL = "qwen3-vl:2b"


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
            {"agent": "primary", "model": PRIMARY_MODEL, "family": ranked[0][0] if ranked else None},
            {"agent": "fallback", "model": FALLBACK_MODEL, "family": ranked[0][0] if ranked else None},
        ],
        "vision_judge_model": VISION_MODEL,
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
    command_successes = 0
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
            commands = attempt.get("commands") or {}
            if isinstance(commands, dict):
                for value in commands.values():
                    if isinstance(value, dict) and value.get("returncode") == 0:
                        command_successes += 1
    return {
        "available": True,
        "subtasks": len(subtasks),
        "attempts": attempts,
        "retry_subtasks": retry_subtasks,
        "feedback_events": feedback_events,
        "native_judge_attempts": native_judge_attempts,
        "successful_native_commands": command_successes,
        "best_scores": best_scores,
        "mean_best_score": statistics.fmean(best_scores) if best_scores else 0.0,
        "completed_all_subtasks": len(subtasks) >= 5,
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
            if row.get("kind") in {"proxy-start", "proxy-stop", "local-model-list"}:
                continue
            rows.append(row)
    usage = Counter()
    tool_calls = 0
    tools_offered = 0
    statuses = Counter()
    models = Counter()
    labels = Counter()
    wall_ms = 0.0
    for row in rows:
        u = row.get("usage") or {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            try:
                usage[key] += int(u.get(key) or 0)
            except Exception:
                pass
        tool_calls += int(row.get("tool_calls") or 0)
        tools_offered += int(row.get("tools_offered") or 0)
        statuses[str(row.get("status"))] += 1
        if row.get("model"):
            models[str(row["model"])] += 1
        if row.get("label"):
            labels[str(row["label"])] += 1
        try:
            wall_ms += float(row.get("wall_ms") or 0.0)
        except Exception:
            pass
    return {
        "model_requests": len(rows),
        "requests_by_role": dict(labels),
        "models": dict(models),
        "statuses": dict(statuses),
        "prompt_tokens_reported": usage["prompt_tokens"],
        "completion_tokens_reported": usage["completion_tokens"],
        "total_tokens_reported": usage["total_tokens"],
        "tool_calls_reported": tool_calls,
        "tools_offered_across_requests": tools_offered,
        "upstream_request_wall_seconds": wall_ms / 1000.0,
        "monetary_cost_usd": 0.0,
        "cost_note": (
            "Models execute locally in Ollama on the GitHub-hosted runner, so there is no external "
            "per-token API charge in this proof. Runner/computing opportunity cost is not converted "
            "into a fabricated dollar amount."
        ),
    }


def report(args: argparse.Namespace) -> dict[str, Any]:
    primary = _score_summary(_load(Path(args.backend_meta)) if args.backend_meta else None)
    fallback = _score_summary(_load(Path(args.backend_fallback_meta)) if args.backend_fallback_meta else None)
    frontend = _score_summary(_load(Path(args.frontend_meta)) if args.frontend_meta else None)
    route = _load(Path(args.route)) if args.route else None
    meter = _meter_summary([Path(p) for p in args.meter])
    runtime = {}
    for item in args.runtime or []:
        key, value = item.split("=", 1)
        try:
            runtime[key] = float(value)
        except Exception:
            runtime[key] = value

    recovery_triggered = bool(fallback.get("available"))
    result = {
        "protocol": (
            "AgencyBench native representative proof: AgentWeave routes Backend/scenario1, one live SII "
            "cumulative implementation pass builds a final workspace covering all five visible Backend "
            "requirements, and the pinned upstream evaluator scores that workspace against all five native "
            "subtask contracts. Frontend/scenario1 subtask1 separately exercises the official Docker/browser "
            "judge path."
        ),
        "routing": route,
        "backend_primary": primary,
        "backend_fallback": fallback,
        "frontend_docker_native_judge": frontend,
        "recovery": {
            "triggered": recovery_triggered,
            "policy": (
                "If primary Backend/scenario1 mean native score < 6 or five-contract evaluation is incomplete, "
                "build a new cumulative workspace with the alternate candidate model and score it against the "
                "same five pinned native contracts."
            ),
        },
        "metering": meter,
        "runtime": runtime,
        "boundaries": [
            (
                "Backend/scenario1 uses all five upstream requirements and all five pinned native rubric contracts. "
                "To remain bounded on a CPU-only hosted runner, the agent produces one cumulative final workspace; "
                "this does not claim five separate SII agent conversations."
            ),
            (
                "The five Backend scores are produced by the upstream AgencyBench evaluator in --eval-only mode "
                "from copies of that cumulative workspace; low scores remain benchmark outcomes and are not rewritten."
            ),
            (
                "Frontend/scenario1 is intentionally limited to subtask1 to exercise the official Docker sandbox "
                "and native frontend evaluation path without claiming a complete Frontend scenario score."
            ),
            (
                "Metered OpenAI-compatible request/token/tool-call counts include only traffic that actually traverses "
                "the local proxy. SII CLI task tool execution is evidenced separately by its native logs and is not "
                "assumed to traverse that proxy."
            ),
            (
                "The controlled model preflight requires actual OpenAI-compatible tool_call objects from both candidate "
                "models before native task execution begins."
            ),
            (
                "Monetary model API cost is $0 for local Ollama inference; GitHub-hosted runner cost is not invented "
                "or inferred from unavailable billing metadata."
            ),
            "This is a representative native slice, not the entire published AgencyBench suite.",
        ],
    }
    Path(args.output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")

    md = [
        "# AgencyBench native end-to-end representative proof",
        "",
        "| Component | Result |",
        "|---|---:|",
        f"| Backend native contracts scored | {primary.get('subtasks', 0)} |",
        f"| Backend primary mean best score | {primary.get('mean_best_score', 0.0):.2f}/10 |",
        f"| Backend primary successful native commands | {primary.get('successful_native_commands', 0)} |",
        f"| Backend native rubric attempts | {primary.get('native_judge_attempts', 0)} |",
        f"| Recovery alternate agent executed | {'yes' if recovery_triggered else 'no'} |",
        f"| Frontend Docker/native judge subtasks | {frontend.get('subtasks', 0)} |",
        f"| Frontend mean best score | {frontend.get('mean_best_score', 0.0):.2f}/10 |",
        f"| Metered proxy requests | {meter.get('model_requests', 0)} |",
        f"| Reported prompt tokens | {meter.get('prompt_tokens_reported', 0)} |",
        f"| Reported completion tokens | {meter.get('completion_tokens_reported', 0)} |",
        f"| Reported total tokens | {meter.get('total_tokens_reported', 0)} |",
        f"| Reported model tool calls | {meter.get('tool_calls_reported', 0)} |",
        "| External model API cost | **$0.00 (local inference)** |",
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
