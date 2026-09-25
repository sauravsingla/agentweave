from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping, Sequence

from .runtime import AgentWeaveRuntime as BaseAgentWeaveRuntime
from .runtime import RoutingPreview
from .runtime_types import (
    ModelResponse,
    RunContext,
    RuntimeResult,
    RuntimeTelemetry,
    ToolCall,
    ToolResult,
    ToolSpec,
)


class AgentWeaveRuntime(BaseAgentWeaveRuntime):
    """Canonical runtime with replay protection and authoritative result provenance.

    Replay protection is scoped to one ``run`` invocation and happens only after the
    existing schema-validation and authorization gates. ``ToolSpec.idempotency`` accepts
    ``auto``, ``none``, ``call_id`` and ``arguments``. ``auto`` uses argument-signature
    protection for high/critical-risk tools and call-ID protection for other tools.
    Only successful executions are cached, so failed calls remain eligible for recovery.
    """

    _IDEMPOTENCY_MODES = frozenset({"auto", "none", "call_id", "arguments"})

    @classmethod
    def _idempotency_mode(cls, tool: ToolSpec) -> str:
        mode = str(tool.idempotency or "auto").strip().lower()
        if mode not in cls._IDEMPOTENCY_MODES:
            raise ValueError(
                f"unsupported idempotency mode {tool.idempotency!r} for tool {tool.key!r}"
            )
        if mode == "auto":
            return (
                "arguments"
                if str(tool.risk_level).lower() in {"high", "critical"}
                else "call_id"
            )
        return mode

    @staticmethod
    def _argument_signature(call: ToolCall, tool: ToolSpec) -> str:
        payload = json.dumps(
            {
                "tool_key": tool.key,
                "arguments": dict(call.arguments),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def _replay_key(cls, call: ToolCall, tool: ToolSpec) -> tuple[str | None, str]:
        mode = cls._idempotency_mode(tool)
        if mode == "none":
            return None, mode
        if mode == "arguments":
            return f"arguments:{cls._argument_signature(call, tool)}", mode
        if call.id:
            return f"call_id:{tool.key}:{call.id}", mode
        # Normalized model responses normally synthesize an ID. Fall back to an
        # argument signature rather than silently dropping replay protection.
        return f"arguments:{cls._argument_signature(call, tool)}", "arguments"

    @staticmethod
    def _authoritative_result(
        *,
        result: ToolResult,
        call: ToolCall,
        tool: ToolSpec,
    ) -> ToolResult:
        """Bind executor output to the identity that passed runtime authorization."""
        reported = {
            "tool_call_id": result.tool_call_id,
            "name": result.name,
            "model_name": result.model_name,
            "tool_key": result.tool_key,
        }
        authoritative = {
            "tool_call_id": call.id,
            "name": tool.name,
            "model_name": tool.exposed_name,
            "tool_key": tool.key,
            "provider": tool.provider,
            "source": tool.source,
        }
        metadata = dict(result.metadata)
        metadata["agentweave_runtime"] = authoritative
        if any(
            (
                reported["tool_call_id"] != call.id,
                reported["name"] != tool.name,
                reported["model_name"] not in {None, tool.exposed_name},
                reported["tool_key"] not in {None, tool.key},
            )
        ):
            metadata["agentweave_executor_reported_identity"] = reported
        return ToolResult(
            tool_call_id=call.id,
            name=tool.name,
            model_name=tool.exposed_name,
            tool_key=tool.key,
            success=result.success,
            content=result.content,
            structured_content=result.structured_content,
            error=result.error,
            metadata=metadata,
            raw=result.raw,
        )

    @staticmethod
    def _replayed_result(
        *,
        cached: ToolResult,
        call: ToolCall,
        tool: ToolSpec,
        mode: str,
    ) -> ToolResult:
        metadata = dict(cached.metadata)
        metadata["agentweave_runtime"] = {
            "tool_call_id": call.id,
            "name": tool.name,
            "model_name": tool.exposed_name,
            "tool_key": tool.key,
            "provider": tool.provider,
            "source": tool.source,
        }
        metadata["agentweave_replay"] = {
            "reused": True,
            "mode": mode,
            "source_tool_call_id": cached.tool_call_id,
        }
        return ToolResult(
            tool_call_id=call.id,
            name=tool.name,
            model_name=tool.exposed_name,
            tool_key=tool.key,
            success=True,
            content=cached.content,
            structured_content=cached.structured_content,
            error=None,
            metadata=metadata,
            raw=cached.raw,
        )

    @staticmethod
    def _finish(
        *,
        status: str,
        response: ModelResponse | None,
        tool_results: Sequence[ToolResult],
        preview: RoutingPreview | None,
        recovery_attempts: int,
        provenance: Mapping[str, Any],
        telemetry: RuntimeTelemetry,
    ) -> RuntimeResult:
        return RuntimeResult(
            status=status,
            response=response,
            tool_results=tuple(tool_results),
            selected_tools=tuple(tool.name for tool in (preview.selected if preview else ())),
            routing_confidence=preview.confidence if preview else None,
            routing_abstained=preview.abstained if preview else False,
            recovery_attempts=recovery_attempts,
            provenance=provenance,
            telemetry=telemetry.as_dict(),
        )

    async def run(
        self,
        text: str,
        *,
        context: RunContext | None = None,
        messages: Sequence[Mapping[str, Any]] | None = None,
        model_kwargs: Mapping[str, Any] | None = None,
    ) -> RuntimeResult:
        ctx = context or RunContext()
        telemetry = RuntimeTelemetry()

        started = time.perf_counter()
        source = self._dedupe(list(await self.catalog.list_tools(ctx)))
        telemetry.record(
            "catalog",
            (time.perf_counter() - started) * 1000.0,
            metadata={"catalog_size": len(source)},
        )

        active_source = list(source)
        conversation = list(messages or [{"role": "user", "content": text}])
        tool_results: list[ToolResult] = []
        execution_ledger: dict[str, ToolResult] = {}
        recovery_attempts = 0
        last_response: ModelResponse | None = None
        last_preview: RoutingPreview | None = None
        failed_keys: set[str] = set()
        run_provenance: dict[str, Any] = {"turns": [], "replays": []}

        for turn in range(self.max_model_turns):
            candidates = [tool for tool in active_source if tool.key not in failed_keys]

            started = time.perf_counter()
            preview = await self.preview_route(text, context=ctx, tools=candidates)
            telemetry.record(
                "scope_route",
                (time.perf_counter() - started) * 1000.0,
                metadata={
                    "turn": turn + 1,
                    "candidate_count": len(candidates),
                    "selected_count": len(preview.selected),
                    "confidence": preview.confidence,
                    "abstained": preview.abstained,
                },
            )
            last_preview = preview

            started = time.perf_counter()
            response = await self._complete(conversation, preview.selected, model_kwargs)
            telemetry.record(
                "model",
                (time.perf_counter() - started) * 1000.0,
                metadata={
                    "turn": turn + 1,
                    "tool_call_count": len(response.tool_calls),
                    "finish_reason": response.finish_reason,
                    "usage": dict(response.usage),
                },
            )
            last_response = response
            run_provenance["turns"].append(
                {
                    "turn": turn + 1,
                    "selected_tools": [
                        {"key": tool.key, "name": tool.name, "model_name": tool.exposed_name}
                        for tool in preview.selected
                    ],
                    "routing_confidence": preview.confidence,
                    "routing_abstained": preview.abstained,
                    "routing": dict(preview.provenance),
                    "tool_calls": [call.name for call in response.tool_calls],
                }
            )

            if not response.tool_calls:
                return self._finish(
                    status="completed",
                    response=response,
                    tool_results=tool_results,
                    preview=preview,
                    recovery_attempts=recovery_attempts,
                    provenance=run_provenance,
                    telemetry=telemetry,
                )

            conversation.append(self._assistant_tool_message(response))
            turn_failed = False

            for raw_call in response.tool_calls:
                call, tool = self._resolve_call(raw_call, preview.selected)
                if tool is None:
                    result = ToolResult(
                        tool_call_id=raw_call.id,
                        name=raw_call.name,
                        model_name=raw_call.name,
                        success=False,
                        error="authorization-denied:tool-not-model-visible",
                    )
                    telemetry.record(
                        "authorization",
                        0.0,
                        outcome="denied",
                        metadata={"model_name": raw_call.name, "reason": "tool-not-model-visible"},
                    )
                    tool_results.append(result)
                    conversation.append(self._tool_message(result))
                    turn_failed = True
                    continue

                started = time.perf_counter()
                validation_error = self._validate_arguments(call, tool)
                telemetry.record(
                    "schema_validation",
                    (time.perf_counter() - started) * 1000.0,
                    outcome="denied" if validation_error else "ok",
                    metadata={"tool_key": tool.key, "tool": tool.name},
                )
                if validation_error:
                    result = ToolResult(
                        tool_call_id=call.id,
                        name=tool.name,
                        model_name=tool.exposed_name,
                        tool_key=tool.key,
                        success=False,
                        error=f"invalid-tool-arguments:{validation_error}",
                    )
                    tool_results.append(result)
                    conversation.append(self._tool_message(result))
                    turn_failed = True
                    continue

                started = time.perf_counter()
                decision = await self._authorize(call, tool, ctx, preview.selected)
                telemetry.record(
                    "authorization",
                    (time.perf_counter() - started) * 1000.0,
                    outcome="ok" if decision.allowed else "denied",
                    metadata={
                        "tool_key": tool.key,
                        "tool": tool.name,
                        "reason": decision.reason_code,
                    },
                )
                if not decision.allowed:
                    result = ToolResult(
                        tool_call_id=call.id,
                        name=tool.name,
                        model_name=tool.exposed_name,
                        tool_key=tool.key,
                        success=False,
                        error=f"authorization-denied:{decision.reason_code}",
                    )
                    failed_keys.add(tool.key)
                else:
                    replay_key, replay_mode = self._replay_key(call, tool)
                    cached = execution_ledger.get(replay_key) if replay_key is not None else None
                    if cached is not None:
                        result = self._replayed_result(
                            cached=cached,
                            call=call,
                            tool=tool,
                            mode=replay_mode,
                        )
                        telemetry.record(
                            "replay",
                            0.0,
                            outcome="reused",
                            metadata={
                                "tool_key": tool.key,
                                "tool": tool.name,
                                "mode": replay_mode,
                                "source_tool_call_id": cached.tool_call_id,
                            },
                        )
                        run_provenance["replays"].append(
                            {
                                "turn": turn + 1,
                                "tool_key": tool.key,
                                "tool": tool.name,
                                "model_name": tool.exposed_name,
                                "mode": replay_mode,
                                "source_tool_call_id": cached.tool_call_id,
                                "replayed_tool_call_id": call.id,
                            }
                        )
                    else:
                        started = time.perf_counter()
                        executor_result = await self.executor.execute(call, ctx)
                        result = self._authoritative_result(
                            result=executor_result,
                            call=call,
                            tool=tool,
                        )
                        telemetry.record(
                            "execution",
                            (time.perf_counter() - started) * 1000.0,
                            outcome="ok" if result.success else "error",
                            metadata={"tool_key": tool.key, "tool": tool.name},
                        )
                        if result.success and replay_key is not None:
                            execution_ledger[replay_key] = result
                    if not result.success:
                        failed_keys.add(tool.key)

                tool_results.append(result)
                conversation.append(self._tool_message(result))
                if not result.success:
                    turn_failed = True

            if turn_failed:
                recovery_attempts += 1
                telemetry.record(
                    "recovery",
                    0.0,
                    outcome="retry" if recovery_attempts <= self.max_recovery_attempts else "exhausted",
                    metadata={"attempt": recovery_attempts},
                )
                if recovery_attempts > self.max_recovery_attempts:
                    return self._finish(
                        status="needs-review",
                        response=response,
                        tool_results=tool_results,
                        preview=preview,
                        recovery_attempts=recovery_attempts,
                        provenance=run_provenance,
                        telemetry=telemetry,
                    )
                continue

        return self._finish(
            status="max-turns",
            response=last_response,
            tool_results=tool_results,
            preview=last_preview,
            recovery_attempts=recovery_attempts,
            provenance=run_provenance,
            telemetry=telemetry,
        )
