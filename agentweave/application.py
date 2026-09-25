from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .config import RuntimeConfig, RuntimeFactory
from .runtime_hardened import AgentWeaveRuntime
from .plugins import PluginManager
from .safe_http import SafeHttpTransport


class AgentWeaveApplication:
    """Own runtime + plugin lifecycle as one async application boundary."""

    def __init__(
        self,
        runtime: AgentWeaveRuntime,
        *,
        plugin_manager: PluginManager | None = None,
    ) -> None:
        self.runtime = runtime
        self.plugin_manager = plugin_manager or PluginManager()
        self._started = False

    @classmethod
    def from_config(
        cls,
        config: RuntimeConfig,
        *,
        discover_plugins: bool = True,
        plugin_manager: PluginManager | None = None,
        http_transport: SafeHttpTransport | None = None,
    ) -> "AgentWeaveApplication":
        manager = plugin_manager or PluginManager()
        if discover_plugins:
            manager.discover()
        registry = manager.configure()
        runtime = RuntimeFactory(
            registry=registry,
            http_transport=http_transport,
        ).build(config)
        return cls(runtime, plugin_manager=manager)

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        **kwargs: Any,
    ) -> "AgentWeaveApplication":
        return cls.from_config(RuntimeConfig.load(path), **kwargs)

    @classmethod
    def from_mcp(
        cls,
        target: Any,
        *,
        model: Any,
        source: str | None = None,
        model_name_prefix: str | None = None,
        plugin_manager: PluginManager | None = None,
        **runtime_kwargs: Any,
    ) -> "AgentWeaveApplication":
        """Create a plug-and-play application around one MCP endpoint/server."""

        from .composition import mcp_runtime

        return cls(
            mcp_runtime(
                target,
                model=model,
                source=source,
                model_name_prefix=model_name_prefix,
                **runtime_kwargs,
            ),
            plugin_manager=plugin_manager,
        )

    @classmethod
    def from_mcps(
        cls,
        targets: Mapping[str, Any],
        *,
        model: Any,
        plugin_manager: PluginManager | None = None,
        **runtime_kwargs: Any,
    ) -> "AgentWeaveApplication":
        """Create one application across multiple MCP servers safely."""

        from .composition import multi_mcp_runtime

        return cls(
            multi_mcp_runtime(targets, model=model, **runtime_kwargs),
            plugin_manager=plugin_manager,
        )

    async def start(self) -> None:
        if self._started:
            return
        await self.runtime.start()
        try:
            await self.plugin_manager.start(self.runtime)
        except Exception:
            await self.runtime.stop()
            raise
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        try:
            await self.plugin_manager.stop()
        finally:
            await self.runtime.stop()
            self._started = False

    async def __aenter__(self) -> "AgentWeaveApplication":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        await self.stop()
        return False

    async def run(self, *args: Any, **kwargs: Any):
        if self._started:
            return await self.runtime.run(*args, **kwargs)
        async with self:
            return await self.runtime.run(*args, **kwargs)
