from __future__ import annotations

import json

import pytest

from agentweave import AgentWeaveRuntime, RunContext, StaticToolCatalog, ToolResult, ToolSpec
from agentweave_byom import ToolRoutingResult


class AllRouter:
    version = "test-all"

    async def aroute(self, text, tools, *, max_tools=8):
        return ToolRoutingResult(
            selected=list(tools[:max_tools]),
            filtered=list(tools[max_tools:]),
            provenance={"router": self.version},
            confidence=1.0,
            abstained=False,
        )


class RecoveryReplayModel:
    def __init__(self):
        self.turn = 0

    async def complete(self, messages, *, tools=None, **kwargs):
        self.turn += 1
        if self.turn == 1:
            calls = [
                {
                    "id": "transfer-1",
                    "type": "function",
                    "function": {"name": "transfer", "arguments": '{"amount":100}'},
                },
                {
                    "id": "fail-1",
                    "type": "function",
                    "function": {"name": "unstable", "arguments": "{}"},
                },
            ]
            return {
                "choices": [
                    {
                        "message": {"content": None, "tool_calls": calls},
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        if self.turn == 2:
            return {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "transfer-2",
                                    "type": "function",
                                    "function": {
                                        "name": "transfer",
                                        "arguments": '{"amount":100}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        return {
            "choices": [
                {
                    "message": {"content": "done", "tool_calls": []},
                    "finish_reason": "stop",
                }
            ]
        }


class SpoofingExecutor:
    def __init__(self):
        self.transfer_calls = 0
        self.unstable_calls = 0

    async def execute(self, call, context):
        if call.name == "unstable":
            self.unstable_calls += 1
            return ToolResult(
                tool_call_id="executor-fail",
                name="executor-unstable",
                model_name="wrong-visible-name",
                tool_key="wrong:key",
                success=False,
                error="simulated-failure",
            )
        self.transfer_calls += 1
        return ToolResult(
            tool_call_id="executor-transfer",
            name="executor-transfer-name",
            model_name="wrong-visible-name",
            tool_key="wrong:key",
            success=True,
            structured_content={"ok": True, "amount": call.arguments["amount"]},
            metadata={"executor": "spoofing-test"},
        )


@pytest.mark.asyncio
async def test_high_risk_argument_replay_is_reused_and_executor_runs_once():
    executor = SpoofingExecutor()
    runtime = AgentWeaveRuntime(
        model=RecoveryReplayModel(),
        catalog=StaticToolCatalog(
            [
                ToolSpec(
                    id="payments:prod:transfer",
                    name="transfer",
                    risk_level="high",
                    input_schema={
                        "type": "object",
                        "properties": {"amount": {"type": "number"}},
                        "required": ["amount"],
                        "additionalProperties": False,
                    },
                ),
                ToolSpec(id="test:unstable", name="unstable"),
            ]
        ),
        executor=executor,
        router=AllRouter(),
        max_tools=2,
        max_model_turns=4,
        max_recovery_attempts=2,
    )

    result = await runtime.run(
        "transfer 100 and verify the unstable step",
        context=RunContext(human_approved=True),
    )

    assert result.status == "completed"
    assert executor.transfer_calls == 1
    assert executor.unstable_calls == 1
    transfer_results = [item for item in result.tool_results if item.name == "transfer"]
    assert len(transfer_results) == 2
    assert transfer_results[0].tool_call_id == "transfer-1"
    assert transfer_results[1].tool_call_id == "transfer-2"
    assert transfer_results[0].tool_key == "payments:prod:transfer"
    assert transfer_results[1].tool_key == "payments:prod:transfer"
    assert transfer_results[1].metadata["agentweave_replay"]["reused"] is True
    assert transfer_results[1].metadata["agentweave_replay"]["mode"] == "arguments"
    assert result.provenance["replays"][0]["source_tool_call_id"] == "transfer-1"
    assert any(
        event["stage"] == "replay" and event["outcome"] == "reused"
        for event in result.telemetry["events"]
    )


@pytest.mark.asyncio
async def test_executor_identity_cannot_override_authorized_runtime_identity():
    executor = SpoofingExecutor()

    class OneShotModel:
        def __init__(self):
            self.called = False

        async def complete(self, messages, *, tools=None, **kwargs):
            if self.called:
                return {"choices": [{"message": {"content": "done", "tool_calls": []}}]}
            self.called = True
            return {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "transfer",
                                        "arguments": '{"amount":7}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }

    runtime = AgentWeaveRuntime(
        model=OneShotModel(),
        catalog=StaticToolCatalog(
            [
                ToolSpec(
                    id="payments:prod:transfer",
                    name="transfer",
                    input_schema={
                        "type": "object",
                        "properties": {"amount": {"type": "number"}},
                        "required": ["amount"],
                    },
                )
            ]
        ),
        executor=executor,
        router=AllRouter(),
    )

    result = await runtime.run("transfer 7")
    tool_result = result.tool_results[0]
    assert tool_result.tool_call_id == "call-1"
    assert tool_result.name == "transfer"
    assert tool_result.model_name == "transfer"
    assert tool_result.tool_key == "payments:prod:transfer"
    assert tool_result.metadata["agentweave_runtime"]["tool_key"] == "payments:prod:transfer"
    assert tool_result.metadata["agentweave_executor_reported_identity"] == {
        "tool_call_id": "executor-transfer",
        "name": "executor-transfer-name",
        "model_name": "wrong-visible-name",
        "tool_key": "wrong:key",
    }


def test_structured_tool_output_is_canonical_json():
    result = ToolResult(
        tool_call_id="c1",
        name="lookup",
        success=True,
        structured_content={"z": [2, 1], "a": True},
    )
    rendered = result.model_content()
    assert rendered == '{"a":true,"z":[2,1]}'
    assert json.loads(rendered) == {"a": True, "z": [2, 1]}


def test_invalid_idempotency_mode_fails_closed_before_execution_keying():
    tool = ToolSpec(name="write", idempotency="sometimes")
    with pytest.raises(ValueError, match="unsupported idempotency mode"):
        AgentWeaveRuntime._idempotency_mode(tool)
