from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .plugins import ComponentRegistry
from .runtime_hardened import AgentWeaveRuntime
from .safe_http import SafeHttpTransport


@dataclass(frozen=True)
class ModelConfig:
    kind: str = "openai-compatible"
    model: str = ""
    base_url: str = ""
    api_key_env: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    timeout: float = 120.0
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CatalogConfig:
    kind: str = "mcp"
    target: str = ""
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutingConfig:
    kind: str = "adaptive"
    max_tools: int = 8
    min_confidence: float = 0.50
    expansion_factor: int = 2
    max_abstention_tools: int = 24
    search_limit: int = 16
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeLimits:
    max_model_turns: int = 4
    max_recovery_attempts: int = 2


@dataclass(frozen=True)
class RuntimeConfig:
    """Typed declarative configuration for the canonical runtime."""

    model: ModelConfig
    catalog: CatalogConfig
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    limits: RuntimeLimits = field(default_factory=RuntimeLimits)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RuntimeConfig":
        data = dict(value)
        model = ModelConfig(**dict(data.get("model") or {}))
        catalog = CatalogConfig(**dict(data.get("catalog") or {}))
        routing = RoutingConfig(**dict(data.get("routing") or {}))
        limits = RuntimeLimits(**dict(data.get("limits") or {}))
        if not model.model:
            raise ValueError("model.model is required")
        if not model.base_url and model.kind == "openai-compatible":
            raise ValueError("model.base_url is required for openai-compatible models")
        if not catalog.target:
            raise ValueError("catalog.target is required")
        return cls(model=model, catalog=catalog, routing=routing, limits=limits)

    @classmethod
    def load(cls, path: str | Path) -> "RuntimeConfig":
        source = Path(path)
        text = source.read_text()
        if source.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml
            except ImportError as exc:
                raise RuntimeError(
                    "Install YAML support with: pip install 'agentweave-router[yaml]'"
                ) from exc
            payload = yaml.safe_load(text) or {}
        else:
            payload = json.loads(text)
        if not isinstance(payload, Mapping):
            raise ValueError("runtime config must be an object")
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": {
                "kind": self.model.kind,
                "model": self.model.model,
                "base_url": self.model.base_url,
                "api_key_env": self.model.api_key_env,
                "headers": dict(self.model.headers),
                "timeout": self.model.timeout,
                "options": dict(self.model.options),
            },
            "catalog": {
                "kind": self.catalog.kind,
                "target": self.catalog.target,
                "options": dict(self.catalog.options),
            },
            "routing": {
                "kind": self.routing.kind,
                "max_tools": self.routing.max_tools,
                "min_confidence": self.routing.min_confidence,
                "expansion_factor": self.routing.expansion_factor,
                "max_abstention_tools": self.routing.max_abstention_tools,
                "search_limit": self.routing.search_limit,
                "options": dict(self.routing.options),
            },
            "limits": {
                "max_model_turns": self.limits.max_model_turns,
                "max_recovery_attempts": self.limits.max_recovery_attempts,
            },
        }


class AgentWeaveBuilder:
    """Programmatic factory for composing runtime components without internals."""

    def __init__(self) -> None:
        self._model: Any = None
        self._catalog: Any = None
        self._executor: Any = None
        self._router: Any = None
        self._scope_policy: Any = None
        self._authorization_policy: Any = None
        self._search_provider: Any = None
        self._options: dict[str, Any] = {}

    def model(self, value: Any) -> "AgentWeaveBuilder":
        self._model = value
        return self

    def catalog(self, value: Any) -> "AgentWeaveBuilder":
        self._catalog = value
        return self

    def executor(self, value: Any) -> "AgentWeaveBuilder":
        self._executor = value
        return self

    def router(self, value: Any) -> "AgentWeaveBuilder":
        self._router = value
        return self

    def scope_policy(self, value: Any) -> "AgentWeaveBuilder":
        self._scope_policy = value
        return self

    def authorization_policy(self, value: Any) -> "AgentWeaveBuilder":
        self._authorization_policy = value
        return self

    def search_provider(self, value: Any) -> "AgentWeaveBuilder":
        self._search_provider = value
        return self

    def options(self, **kwargs: Any) -> "AgentWeaveBuilder":
        self._options.update(kwargs)
        return self

    def build(self) -> AgentWeaveRuntime:
        missing = [
            name
            for name, value in (
                ("model", self._model),
                ("catalog", self._catalog),
                ("executor", self._executor),
            )
            if value is None
        ]
        if missing:
            raise ValueError(f"missing runtime components: {', '.join(missing)}")
        return AgentWeaveRuntime(
            model=self._model,
            catalog=self._catalog,
            executor=self._executor,
            router=self._router,
            scope_policy=self._scope_policy,
            authorization_policy=self._authorization_policy,
            search_provider=self._search_provider,
            **self._options,
        )


class RuntimeFactory:
    """Build AgentWeaveRuntime from typed config plus optional plugin components."""

    def __init__(
        self,
        registry: ComponentRegistry | None = None,
        *,
        http_transport: SafeHttpTransport | None = None,
    ) -> None:
        self.registry = registry or ComponentRegistry()
        self.http_transport = http_transport or SafeHttpTransport()

    @staticmethod
    def _plugin_component(bucket: Mapping[str, Any], kind: str, config: Any) -> Any:
        component = bucket[kind]
        return component(config) if callable(component) else component

    def _model(self, config: ModelConfig) -> Any:
        if config.kind == "openai-compatible":
            from agentweave_byom import OpenAICompatibleModelAdapter

            api_key = os.environ.get(config.api_key_env) if config.api_key_env else None
            return OpenAICompatibleModelAdapter(
                model=config.model,
                base_url=config.base_url,
                api_key=api_key,
                headers=config.headers,
                timeout=config.timeout,
                transport=self.http_transport,
            )
        if config.kind in self.registry.models:
            return self._plugin_component(self.registry.models, config.kind, config)
        raise ValueError(f"unknown model kind: {config.kind}")

    def _catalog_and_executor(self, config: CatalogConfig) -> tuple[Any, Any]:
        if config.kind == "mcp":
            from .integrations.mcp import MCPConnection, MCPExecutor, MCPToolCatalog

            options = dict(config.options)
            source = options.pop("source", None)
            if options:
                unknown = ", ".join(sorted(options))
                raise ValueError(f"unsupported declarative MCP options: {unknown}")
            connection = MCPConnection(
                config.target,
                http_guard=self.http_transport,
            )
            return (
                MCPToolCatalog(connection=connection, source=source),
                MCPExecutor(connection=connection),
            )
        if config.kind in self.registry.catalogs:
            catalog = self._plugin_component(
                self.registry.catalogs,
                config.kind,
                config,
            )
            if config.kind not in self.registry.executors:
                raise ValueError(
                    f"catalog kind {config.kind!r} has no matching executor plugin"
                )
            executor = self._plugin_component(
                self.registry.executors,
                config.kind,
                config,
            )
            return catalog, executor
        raise ValueError(f"unknown catalog kind: {config.kind}")

    def _router(self, config: RoutingConfig) -> Any:
        from agentweave_byom import (
            AdaptiveRouter,
            ConfidencePolicy,
            DeterministicRouterV1,
        )

        if config.kind == "deterministic":
            return DeterministicRouterV1()
        if config.kind == "adaptive":
            return AdaptiveRouter(
                DeterministicRouterV1(),
                confidence_policy=ConfidencePolicy(
                    min_confidence=config.min_confidence,
                    expansion_factor=config.expansion_factor,
                    max_abstention_tools=config.max_abstention_tools,
                    search_limit=config.search_limit,
                ),
            )
        if config.kind in self.registry.routers:
            return self._plugin_component(
                self.registry.routers,
                config.kind,
                config,
            )
        raise ValueError(f"unknown routing kind: {config.kind}")

    def build(self, config: RuntimeConfig) -> AgentWeaveRuntime:
        catalog, executor = self._catalog_and_executor(config.catalog)
        return AgentWeaveRuntime(
            model=self._model(config.model),
            catalog=catalog,
            executor=executor,
            router=self._router(config.routing),
            max_tools=config.routing.max_tools,
            search_limit=config.routing.search_limit,
            max_model_turns=config.limits.max_model_turns,
            max_recovery_attempts=config.limits.max_recovery_attempts,
        )

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        registry: ComponentRegistry | None = None,
        http_transport: SafeHttpTransport | None = None,
    ) -> AgentWeaveRuntime:
        config = RuntimeConfig.load(path)
        return cls(
            registry=registry,
            http_transport=http_transport,
        ).build(config)
