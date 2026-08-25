from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Callable, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class ScopeContext:
    role: str | None = None
    tenant: str | None = None
    identity: str | None = None
    permissions: frozenset[str] = frozenset()
    scopes: frozenset[str] = frozenset()
    environment: str | None = None


@dataclass(frozen=True)
class ScopedTool:
    name: str
    roles: frozenset[str] = frozenset()
    tenants: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    scopes: frozenset[str] = frozenset()
    environments: frozenset[str] = frozenset()
    audience: frozenset[str] = frozenset()
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True)
class ScopeDecision:
    tool: str
    allowed: bool
    reason_code: str


@dataclass(frozen=True)
class ScopeProvenance:
    source_catalog_hash: str
    source_catalog_size: int
    policy_version: str
    context_fingerprint: str
    resulting_catalog_hash: str
    resulting_catalog_size: int
    routed_catalog_hash: str | None = None
    routed_catalog_size: int | None = None
    router_version: str | None = None


@dataclass(frozen=True)
class ScopeFilterResult:
    tools: tuple[ScopedTool, ...]
    decisions: tuple[ScopeDecision, ...]
    provenance: ScopeProvenance

    @property
    def dropped(self) -> tuple[ScopeDecision, ...]:
        return tuple(item for item in self.decisions if not item.allowed)


@dataclass(frozen=True)
class PolicyRoutingResult:
    policy_tools: tuple[ScopedTool, ...]
    model_visible_tools: tuple[ScopedTool, ...]
    decisions: tuple[ScopeDecision, ...]
    provenance: ScopeProvenance
    router_applied: bool


ToolRouter = Callable[[Sequence[ScopedTool]], Sequence[ScopedTool]]


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _tool_record(tool: ScopedTool) -> dict:
    return {
        "name": tool.name,
        "roles": sorted(tool.roles),
        "tenants": sorted(tool.tenants),
        "permissions": sorted(tool.permissions),
        "scopes": sorted(tool.scopes),
        "environments": sorted(tool.environments),
        "audience": sorted(tool.audience),
        "metadata": dict(tool.metadata or {}),
    }


def catalog_hash(tools: Iterable[ScopedTool]) -> str:
    return _stable_hash([_tool_record(tool) for tool in tools])


def context_fingerprint(context: ScopeContext) -> str:
    return _stable_hash({
        "role": context.role,
        "tenant": context.tenant,
        "identity": context.identity,
        "permissions": sorted(context.permissions),
        "scopes": sorted(context.scopes),
        "environment": context.environment,
    })


class StaticScopeFilter:
    """Deterministic pre-model scope filter.

    Restrictions are conjunctive across dimensions and fail closed: if a tool
    declares a restriction for a dimension, the caller context must satisfy it.
    Tools with no restrictions on a dimension are not rejected by that dimension.
    """

    def __init__(self, *, policy_version: str = "scope-v1") -> None:
        self.policy_version = policy_version

    def decide(self, tool: ScopedTool, context: ScopeContext) -> ScopeDecision:
        if tool.roles and context.role not in tool.roles:
            return ScopeDecision(tool.name, False, "role_not_allowed")
        if tool.tenants and context.tenant not in tool.tenants:
            return ScopeDecision(tool.name, False, "tenant_not_allowed")
        if tool.environments and context.environment not in tool.environments:
            return ScopeDecision(tool.name, False, "environment_not_allowed")
        if tool.permissions and not tool.permissions.issubset(context.permissions):
            return ScopeDecision(tool.name, False, "missing_permission")
        if tool.scopes and not tool.scopes.issubset(context.scopes):
            return ScopeDecision(tool.name, False, "missing_scope")
        if tool.audience:
            audience_values = {value for value in (context.role, context.tenant, context.environment) if value}
            if tool.audience.isdisjoint(audience_values):
                return ScopeDecision(tool.name, False, "audience_mismatch")
        return ScopeDecision(tool.name, True, "allowed")

    def filter(self, tools: Iterable[ScopedTool], context: ScopeContext) -> ScopeFilterResult:
        source = tuple(tools)
        decisions = tuple(self.decide(tool, context) for tool in source)
        allowed_names = {decision.tool for decision in decisions if decision.allowed}
        allowed = tuple(tool for tool in source if tool.name in allowed_names)
        provenance = ScopeProvenance(
            source_catalog_hash=catalog_hash(source),
            source_catalog_size=len(source),
            policy_version=self.policy_version,
            context_fingerprint=context_fingerprint(context),
            resulting_catalog_hash=catalog_hash(allowed),
            resulting_catalog_size=len(allowed),
        )
        return ScopeFilterResult(allowed, decisions, provenance)


def apply_policy_then_optional_routing(
    *,
    tools: Iterable[ScopedTool],
    context: ScopeContext,
    scope_filter: StaticScopeFilter,
    router: ToolRouter | None = None,
    router_version: str | None = None,
) -> PolicyRoutingResult:
    """Apply deterministic policy first; route only the permitted subset.

    This makes dynamic routing optional and guarantees policy-denied tools never
    reach the router or the model-visible set.
    """
    filtered = scope_filter.filter(tools, context)
    policy_tools = filtered.tools

    if router is None:
        return PolicyRoutingResult(
            policy_tools=policy_tools,
            model_visible_tools=policy_tools,
            decisions=filtered.decisions,
            provenance=filtered.provenance,
            router_applied=False,
        )

    routed = tuple(router(policy_tools))
    permitted_names = {tool.name for tool in policy_tools}
    if any(tool.name not in permitted_names for tool in routed):
        raise ValueError("router returned a tool excluded by deterministic scope policy")

    provenance = ScopeProvenance(
        **{**asdict(filtered.provenance),
           "routed_catalog_hash": catalog_hash(routed),
           "routed_catalog_size": len(routed),
           "router_version": router_version or "unspecified"}
    )
    return PolicyRoutingResult(
        policy_tools=policy_tools,
        model_visible_tools=routed,
        decisions=filtered.decisions,
        provenance=provenance,
        router_applied=True,
    )
