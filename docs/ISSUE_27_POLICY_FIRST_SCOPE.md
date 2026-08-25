# Issue #27 Policy-First Scope Filtering

AgentWeave should first apply deterministic caller-context policy before deciding whether dynamic task-aware routing is necessary.

## Architecture

```text
source catalog
  -> deterministic scope/policy filter
  -> optional task-aware router
  -> model-visible tools
  -> model selection
  -> fail-closed authorization
  -> execution / verification / recovery
```

The scope stage is deterministic and independent of model reasoning. Dynamic routing is optional.

## Supported deterministic dimensions

`StaticScopeFilter` can restrict tools using:

- caller role;
- tenant;
- required permissions;
- required scopes;
- deployment environment;
- audience tags.

If a tool declares a restriction, the caller must satisfy it. Missing required policy context fails closed for that tool.

## Reason codes

Dropped tools receive explicit reason codes such as:

- `role_not_allowed`;
- `tenant_not_allowed`;
- `environment_not_allowed`;
- `missing_permission`;
- `missing_scope`;
- `audience_mismatch`.

Allowed tools receive `allowed`.

## Provenance

Every deterministic filtering result records:

- source catalog hash and size;
- policy version;
- caller-context fingerprint;
- resulting permitted catalog hash and size.

When routing is applied, provenance additionally records:

- router version;
- routed model-visible catalog hash and size.

A router is prevented from reintroducing any tool excluded by deterministic policy.

## Policy-only execution

When deterministic scope reduction is sufficient, the router may be omitted:

```text
catalog -> policy filter -> model
```

This avoids unnecessary semantic-routing cost and preserves an auditable deterministic reduction path.

## Policy + routing execution

When the permitted catalog remains large, routing can narrow it further:

```text
catalog -> policy filter -> router -> model
```

Only policy-permitted tools reach the router.

## Controlled comparison

The bundled deterministic benchmark compares:

1. all-tools exposure;
2. policy-only reduction;
3. policy + task routing.

It records model-visible candidates, candidate reduction, policy-denied exposure, relevant-tool survival, task success, an input-token proxy, and explicit policy/routing/model latency proxies.

The default scenario is designed so all three conditions retain the required `lookup` tool, while policy filtering removes role/tenant/environment-incompatible tools and optional routing reduces the remaining set further.

## Evidence boundary

The benchmark is a deterministic architectural comparison. Token and latency fields are modeled proxies, not production measurements, and the work does not modify frozen BFCL-derived results or historical router evidence.
