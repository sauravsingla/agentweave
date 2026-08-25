from agentweave.failure_analysis import (
    FailureStage,
    classify_failure_stage,
    summarize_recovery,
    summarize_stage_outcomes,
)


def _outcome(**overrides):
    values = {
        "required_tools_survived": True,
        "selected_required_tools": True,
        "composition_complete": True,
        "arguments_valid": True,
        "calls_executable": True,
        "task_success": True,
    }
    values.update(overrides)
    return classify_failure_stage(**values)


def test_failure_taxonomy_uses_earliest_failed_stage():
    assert _outcome(required_tools_survived=False, selected_required_tools=False).failure_stage == FailureStage.ROUTING
    assert _outcome(selected_required_tools=False, composition_complete=False).failure_stage == FailureStage.SELECTION
    assert _outcome(composition_complete=False, calls_executable=False).failure_stage == FailureStage.COMPOSITION
    assert _outcome(arguments_valid=False).failure_stage == FailureStage.EXECUTION
    assert _outcome(calls_executable=False).failure_stage == FailureStage.EXECUTION
    assert _outcome(task_success=False).failure_stage == FailureStage.EXECUTION
    assert _outcome().failure_stage == FailureStage.NONE


def test_outcome_schema_matches_issue_29_contract():
    row = _outcome(task_success=False).to_dict()
    assert row == {
        "required_tools_survived": True,
        "selected_required_tools": True,
        "composition_complete": True,
        "arguments_valid": True,
        "calls_executable": True,
        "task_success": False,
        "failure_stage": "execution",
    }


def test_stage_summary_preserves_task_success_separately():
    summary = summarize_stage_outcomes([
        _outcome(),
        _outcome(required_tools_survived=False, task_success=False),
        _outcome(selected_required_tools=False, task_success=False),
    ])

    assert summary["tasks"] == 3
    assert summary["task_successes"] == 1
    assert summary["failure_stage_counts"]["none"] == 1
    assert summary["failure_stage_counts"]["routing"] == 1
    assert summary["failure_stage_counts"]["selection"] == 1


def test_recovery_summary_separates_attempts_from_final_success():
    summary = summarize_recovery(
        [
            {"attempt": 1, "success": False},
            {"attempt": 2, "success": True},
        ],
        final_task_success=True,
    )

    assert summary == {
        "rerouting_events": 2,
        "successful_recoveries": 1,
        "failed_recovery_attempts": 1,
        "recovery_success": True,
        "final_task_success": True,
    }
