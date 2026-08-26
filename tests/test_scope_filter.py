from agentweave_security.scope_filter import (
    ScopeContext,
    ScopedTool,
    StaticScopeFilter,
    apply_policy_then_optional_routing,
)


def _catalog():
    return (
        ScopedTool("lookup", roles=frozenset({"analyst"}), permissions=frozenset({"read"})),
        ScopedTool("admin_export", roles=frozenset({"admin"}), permissions=frozenset({"export"})),
        ScopedTool("tenant_a_only", tenants=frozenset({"tenant-a"})),
        ScopedTool("prod_only", environments=frozenset({"prod"})),
        ScopedTool("public_help"),
    )


def test_policy_filter_is_deterministic_and_reason_coded():
    context = ScopeContext(
        role="analyst",
        tenant="tenant-a",
        permissions=frozenset({"read"}),
        environment="prod",
    )
    result = StaticScopeFilter(policy_version="policy-7").filter(_catalog(), context)

    assert [tool.name for tool in result.tools] == ["lookup", "tenant_a_only", "prod_only", "public_help"]
    denied = {decision.tool: decision.reason_code for decision in result.dropped}
    assert denied == {"admin_export": "role_not_allowed"}
    assert result.provenance.policy_version == "policy-7"
    assert result.provenance.source_catalog_size == 5
    assert result.provenance.resulting_catalog_size == 4
    assert len(result.provenance.source_catalog_hash) == 64
    assert len(result.provenance.resulting_catalog_hash) == 64


def test_missing_permissions_fail_closed():
    context = ScopeContext(role="analyst", permissions=frozenset())
    result = StaticScopeFilter().filter((ScopedTool("lookup", permissions=frozenset({"read"})),), context)
    assert result.tools == ()
    assert result.decisions[0].reason_code == "missing_permission"


def test_policy_only_path_skips_dynamic_router():
    called = False

    def router(tools):
        nonlocal called
        called = True
        return tools

    result = apply_policy_then_optional_routing(
        tools=_catalog(),
        context=ScopeContext(role="analyst", tenant="tenant-a", permissions=frozenset({"read"}), environment="prod"),
        scope_filter=StaticScopeFilter(),
        router=None,
    )

    assert called is False
    assert result.router_applied is False
    assert result.model_visible_tools == result.policy_tools
    assert result.provenance.routed_catalog_hash is None


def test_denied_tools_never_reach_router_or_model():
    seen_by_router = []

    def router(tools):
        seen_by_router.extend(tool.name for tool in tools)
        return tuple(tool for tool in tools if tool.name == "lookup")

    result = apply_policy_then_optional_routing(
        tools=_catalog(),
        context=ScopeContext(role="analyst", tenant="tenant-a", permissions=frozenset({"read"}), environment="prod"),
        scope_filter=StaticScopeFilter(policy_version="policy-1"),
        router=router,
        router_version="router-v7",
    )

    assert "admin_export" not in seen_by_router
    assert [tool.name for tool in result.model_visible_tools] == ["lookup"]
    assert result.router_applied is True
    assert result.provenance.router_version == "router-v7"
    assert result.provenance.routed_catalog_size == 1


def test_router_cannot_reintroduce_policy_denied_tool():
    denied = ScopedTool("admin_export", roles=frozenset({"admin"}))
    allowed = ScopedTool("lookup", roles=frozenset({"analyst"}))

    def bad_router(_tools):
        return (denied,)

    try:
        apply_policy_then_optional_routing(
            tools=(allowed, denied),
            context=ScopeContext(role="analyst"),
            scope_filter=StaticScopeFilter(),
            router=bad_router,
        )
    except ValueError as exc:
        assert "excluded by deterministic scope policy" in str(exc)
    else:
        raise AssertionError("policy-denied tool was reintroduced")


def test_hashes_are_stable_for_same_inputs():
    context = ScopeContext(role="analyst", tenant="tenant-a", permissions=frozenset({"read"}), environment="prod")
    scope_filter = StaticScopeFilter(policy_version="stable")
    first = scope_filter.filter(_catalog(), context)
    second = scope_filter.filter(_catalog(), context)
    assert first.provenance == second.provenance
