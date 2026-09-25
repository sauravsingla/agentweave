from __future__ import annotations

import importlib
import warnings

from .application import AgentWeaveApplication
from .composition import (
    AliasedToolCatalog,
    CompositeToolCatalog,
    KeyPrefixExecutor,
    mcp_runtime,
    multi_mcp_runtime,
)
from .config import (
    AgentWeaveBuilder,
    CatalogConfig,
    ModelConfig,
    RoutingConfig,
    RuntimeConfig,
    RuntimeFactory,
    RuntimeLimits,
)
from .orchestrator import AgentWeave
from .plugins import (
    PLUGIN_API_VERSION,
    AgentWeavePlugin,
    ComponentRegistry,
    PluginManager,
)
from .runtime import (
    CallableExecutor,
    CatalogProvider,
    DefaultScopePolicy,
    Executor,
    RoutingPreview,
    RuntimeAuthorizationPolicy,
    ScopePolicy,
    StaticToolCatalog,
    ToolAuthorizationPolicy,
    ToolSearchProvider,
    normalize_model_response,
)
from .runtime_hardened import AgentWeaveRuntime
from .runtime_types import (
    ModelResponse,
    RunContext,
    RuntimeResult,
    RuntimeStageEvent,
    RuntimeTelemetry,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from .safe_http import SafeHttpTransport

__version__ = "0.7.1"

__all__ = [
    "AgentWeave",
    "AgentWeaveApplication",
    "AgentWeaveRuntime",
    "ToolSpec",
    "ToolCall",
    "ToolResult",
    "ModelResponse",
    "RunContext",
    "RuntimeResult",
    "RuntimeStageEvent",
    "RuntimeTelemetry",
    "RoutingPreview",
    "CatalogProvider",
    "Executor",
    "ScopePolicy",
    "ToolAuthorizationPolicy",
    "ToolSearchProvider",
    "StaticToolCatalog",
    "CallableExecutor",
    "DefaultScopePolicy",
    "RuntimeAuthorizationPolicy",
    "normalize_model_response",
    "CompositeToolCatalog",
    "AliasedToolCatalog",
    "KeyPrefixExecutor",
    "mcp_runtime",
    "multi_mcp_runtime",
    "RuntimeConfig",
    "ModelConfig",
    "CatalogConfig",
    "RoutingConfig",
    "RuntimeLimits",
    "AgentWeaveBuilder",
    "RuntimeFactory",
    "SafeHttpTransport",
    "AgentWeavePlugin",
    "ComponentRegistry",
    "PluginManager",
    "PLUGIN_API_VERSION",
]

_LEGACY_MODULES = (
    "agentweave.models",
    "agentweave.requirements",
    "agentweave.graph",
    "agentweave.advanced_graph",
    "agentweave.engine",
    "agentweave.optimizer",
    "agentweave.validation",
    "agentweave.semantic",
    "agentweave.discovery",
    "agentweave.marketplaces",
    "agentweave.a2a",
    "agentweave.interoperability",
    "agentweave.lifecycle",
    "agentweave.protocol_depth",
    "agentweave.edge",
    "agentweave.edge_lab",
    "agentweave.identity",
    "agentweave.identity_proof",
    "agentweave.sandbox",
    "agentweave.security_lab",
    "agentweave.storage",
    "agentweave.storage_proof",
    "agentweave.chaos",
    "agentweave.observability",
    "agentweave.policy",
    "agentweave.benchmarks",
    "agentweave.research",
    "agentweave.sdk",
    "agentweave.native",
    "agentweave.recovery",
    "agentweave.workflow",
    "agentweave.durable",
)


_LEGACY_ROOT_INDEX: dict[str, tuple[str, object]] = {}
_LEGACY_SCANNED_MODULES: set[str] = set()


def _index_legacy_module(module_name: str) -> None:
    module = importlib.import_module(module_name)
    exported = getattr(module, "__all__", None)
    names = exported if exported is not None else (
        attr for attr in vars(module) if not attr.startswith("_")
    )
    for attr in names:
        if attr in globals():
            continue
        try:
            value = getattr(module, attr)
        except AttributeError:
            continue
        _LEGACY_ROOT_INDEX.setdefault(attr, (module_name, value))
    _LEGACY_SCANNED_MODULES.add(module_name)


def __getattr__(name: str):
    indexed = _LEGACY_ROOT_INDEX.get(name)
    if indexed is None:
        for module_name in _LEGACY_MODULES:
            if module_name in _LEGACY_SCANNED_MODULES:
                continue
            _index_legacy_module(module_name)
            indexed = _LEGACY_ROOT_INDEX.get(name)
            if indexed is not None:
                break
    if indexed is not None:
        module_name, value = indexed
        warnings.warn(
            f"agentweave.{name} is a legacy root import and is not part of the "
            f"pre-1.0 stable surface; import it from {module_name} instead",
            DeprecationWarning,
            stacklevel=2,
        )
        globals()[name] = value
        return value
    raise AttributeError(f"module 'agentweave' has no attribute {name!r}")
