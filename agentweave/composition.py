from __future__ import annotations

import inspect
import re
from typing import Any, Mapping, Sequence

from .runtime import CatalogProvider, Executor
from .runtime_hardened import AgentWeaveRuntime
from .runtime_types import RunContext, ToolCall, ToolResult, ToolSpec


class CompositeToolCatalog:
    """Combine multiple catalog providers while preserving canonical tool identity."""

    def __init__(self, catalogs: Sequence[CatalogProvider]):
        self.catalogs = tuple(catalogs)

    async def start(self) -> None:
        started: list[CatalogProvider] = []
        try:
            for catalog in self.catalogs:
                hook = getattr(catalog, "start", None)
                if hook is None:
                    continue
                result = hook()
                if inspect.isawaitable(result):
                    await result
                started.append(catalog)
        except BaseException:
            for catalog in reversed(started):
                hook = getattr(catalog, "stop", None)
                if hook is None:
                    continue
                try:
                    result = hook()
                    if inspect.isawaitable(result):
                        await result
                except BaseException:
                    pass
            raise

    async def stop(self) -> None:
        first_error: Exception | None = None
        for catalog in reversed(self.catalogs):
            hook = getattr(catalog, "stop", None)
            if hook is None:
                continue
            try:
                result = hook()
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # preserve best-effort shutdown
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    async def list_tools(self, context: RunContext) -> list[ToolSpec]:
        tools: list[ToolSpec] = []
        for catalog in self.catalogs:
            tools.extend(await catalog.list_tools(context))
        return tools


class AliasedToolCatalog:
    """Assign deterministic model-visible aliases without changing native tool names."""

    def __init__(self, catalog: CatalogProvider, *, prefix: str):
        self.catalog = catalog
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", prefix).strip("_")
        if not cleaned:
            raise ValueError("alias prefix must contain at least one alphanumeric character")
        self.prefix = cleaned

    async def start(self) -> None:
        hook = getattr(self.catalog, "start", None)
        if hook is not None:
            result = hook()
            if inspect.isawaitable(result):
                await result

    async def stop(self) -> None:
        hook = getattr(self.catalog, "stop", None)
        if hook is not None:
            result = hook()
            if inspect.isawaitable(result):
                await result

    async def list_tools(self, context: RunContext) -> list[ToolSpec]:
        from dataclasses import replace

        return [
            replace(tool, model_name=f"{self.prefix}__{tool.name}")
            for tool in await self.catalog.list_tools(context)
        ]


class KeyPrefixExecutor:
    """Dispatch normalized calls by canonical ``tool_key`` prefix."""

    def __init__(self, routes: Mapping[str, Executor]):
        if not routes:
            raise ValueError("at least one executor route is required")
        self.routes = dict(routes)

    async def start(self) -> None:
        seen: set[int] = set()
        started: list[Executor] = []
        try:
            for executor in self.routes.values():
                if id(executor) in seen:
                    continue
                seen.add(id(executor))
                hook = getattr(executor, "start", None)
                if hook is None:
                    continue
                result = hook()
                if inspect.isawaitable(result):
                    await result
                started.append(executor)
        except BaseException:
            for executor in reversed(started):
                hook = getattr(executor, "stop", None)
                if hook is None:
                    continue
                try:
                    result = hook()
                    if inspect.isawaitable(result):
                        await result
                except BaseException:
                    pass
            raise

    async def stop(self) -> None:
        seen: set[int] = set()
        first_error: Exception | None = None
        for executor in reversed(tuple(self.routes.values())):
            if id(executor) in seen:
                continue
            seen.add(id(executor))
            hook = getattr(executor, "stop", None)
            if hook is None:
                continue
            try:
                result = hook()
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    async def execute(self, call: ToolCall, context: RunContext) -> ToolResult:
        key = call.tool_key or ""
        matches = [
            (prefix, executor)
            for prefix, executor in self.routes.items()
            if key.startswith(prefix)
        ]
        if not matches:
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                model_name=call.model_name,
                tool_key=call.tool_key,
                success=False,
                error="no-executor-for-tool-key",
            )
        prefix, executor = max(matches, key=lambda item: len(item[0]))
        del prefix
        return await executor.execute(call, context)


def mcp_runtime(
    target: Any,
    *,
    model: Any,
    source: str | None = None,
    model_name_prefix: str | None = None,
    **runtime_kwargs: Any,
) -> AgentWeaveRuntime:
    """Create a lifecycle-safe runtime for one MCP endpoint/server object."""

    from .integrations.mcp import MCPConnection, MCPExecutor, MCPToolCatalog

    connection = MCPConnection(target)
    catalog: CatalogProvider = MCPToolCatalog(connection=connection, source=source)
    if model_name_prefix:
        catalog = AliasedToolCatalog(catalog, prefix=model_name_prefix)
    return AgentWeaveRuntime(
        model=model,
        catalog=catalog,
        executor=MCPExecutor(connection=connection),
        **runtime_kwargs,
    )


def multi_mcp_runtime(
    targets: Mapping[str, Any],
    *,
    model: Any,
    **runtime_kwargs: Any,
) -> AgentWeaveRuntime:
    """Create one runtime across several MCP servers with collision-safe aliases.

    Every model-visible name is prefixed with the logical source name while native MCP
    calls still use the original tool name. Execution is dispatched by canonical
    ``tool_key`` so identical native names on different servers remain unambiguous.
    """

    from .integrations.mcp import MCPConnection, MCPExecutor, MCPToolCatalog

    if not targets:
        raise ValueError("at least one MCP target is required")
    catalogs: list[CatalogProvider] = []
    routes: dict[str, Executor] = {}
    for source, target in targets.items():
        source_name = str(source)
        connection = MCPConnection(target)
        native_catalog = MCPToolCatalog(connection=connection, source=source_name)
        catalogs.append(AliasedToolCatalog(native_catalog, prefix=source_name))
        routes[f"mcp:{source_name}:"] = MCPExecutor(connection=connection)
    return AgentWeaveRuntime(
        model=model,
        catalog=CompositeToolCatalog(catalogs),
        executor=KeyPrefixExecutor(routes),
        **runtime_kwargs,
    )
