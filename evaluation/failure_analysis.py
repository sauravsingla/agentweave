from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable


class FailureStage(str, Enum):
    ROUTING = "routing"
    SELECTION = "selection"
    COMPOSITION = "composition"
    EXECUTION = "execution"
    NONE = "none"


@dataclass(frozen=True)
class StageOutcome:
    """Stage-level outcome for a routed tool/function-calling task.

    The earliest failed stage is reported without altering the underlying
    benchmark score. This lets historical runs be re-analysed while preserving
    frozen success metrics.
    """

    required_tools_survived: bool
    selected_required_tools: bool
    composition_complete: bool
    arguments_valid: bool
    calls_executable: bool
    task_success: bool
    failure_stage: FailureStage

    def to_dict(self) -> dict:
        row = asdict(self)
        row["failure_stage"] = self.failure_stage.value
        return row


def classify_failure_stage(
    *,
    required_tools_survived: bool,
    selected_required_tools: bool,
    composition_complete: bool,
    arguments_valid: bool,
    calls_executable: bool,
    task_success: bool,
) -> StageOutcome:
    """Classify a task at the earliest failed evaluation stage."""
    if not required_tools_survived:
        stage = FailureStage.ROUTING
    elif not selected_required_tools:
        stage = FailureStage.SELECTION
    elif not composition_complete:
        stage = FailureStage.COMPOSITION
    elif not arguments_valid or not calls_executable or not task_success:
        stage = FailureStage.EXECUTION
    else:
        stage = FailureStage.NONE

    return StageOutcome(
        required_tools_survived=required_tools_survived,
        selected_required_tools=selected_required_tools,
        composition_complete=composition_complete,
        arguments_valid=arguments_valid,
        calls_executable=calls_executable,
        task_success=task_success,
        failure_stage=stage,
    )


def summarize_stage_outcomes(outcomes: Iterable[StageOutcome]) -> dict:
    """Return counts/rates for stage outcomes without changing source scores."""
    rows = list(outcomes)
    total = len(rows)
    counts = {stage.value: 0 for stage in FailureStage}
    for row in rows:
        counts[row.failure_stage.value] += 1

    rates = {
        name: (count / total if total else 0.0)
        for name, count in counts.items()
    }
    return {
        "tasks": total,
        "failure_stage_counts": counts,
        "failure_stage_rates": rates,
        "task_successes": sum(1 for row in rows if row.task_success),
    }


def summarize_recovery(events: Iterable[dict], final_task_success: bool) -> dict:
    """Summarize recovery attempts independently from final task success."""
    rows = list(events)
    successful = [row for row in rows if row.get("success")]
    failed = [row for row in rows if not row.get("success")]
    return {
        "rerouting_events": len(rows),
        "successful_recoveries": len(successful),
        "failed_recovery_attempts": len(failed),
        "recovery_success": bool(successful),
        "final_task_success": bool(final_task_success),
    }
