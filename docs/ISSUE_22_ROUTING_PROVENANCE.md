# Issue #22: Portable Tool-Routing Provenance

AgentWeave should let a downstream consumer distinguish tools that were unavailable to the model from tools that were visible but not selected, without exposing private model reasoning.

## Portable record

`ToolRoutingProvenance` captures the observable decision path:

```text
source catalog
  -> deterministic policy filtering
  -> optional task-aware routing
  -> model-visible tool set
  -> model/function call
  -> fail-closed authorization
  -> execution / recovery outcome
```

The record includes:

- source catalog names and stable catalog hash;
- policy version and caller-context fingerprint;
- tools removed by policy and reason codes;
- tools permitted by policy;
- whether routing ran and the router version;
- tools removed by routing;
- model-visible tools;
- selected function/action and arguments/call identifier when supplied;
- authorization result and reason;
- execution success/result code;
- recovery attempted/success fields;
- stage telemetry from the authorization/observability layer;
- deterministic JSON serialization and a SHA-256 record hash.

## Privacy boundary

The artifact records externally observable decisions and execution state only. It intentionally does not contain hidden chain-of-thought, model scratchpads, private reasoning traces, or router internal reasoning.

## Relationship to later issues

Issue #27 provides deterministic policy-first scope filtering and routing provenance inputs. Issue #28 provides fail-closed authorization and stage telemetry. Issue #29 provides recovery/failure-stage evaluation. This issue integrates those signals into one portable record instead of introducing a parallel routing mechanism.

## Example interpretation

If `admin_export` is removed by policy while `verify` survives policy but is removed by routing, the record makes that distinction explicit. If the model then selects `lookup`, the artifact can show whether authorization allowed it, whether execution succeeded, and whether recovery was required.

## Evidence boundary

This is an architectural and observability capability. It does not modify frozen BFCL-derived scores or historical benchmark artifacts, and it should not be presented as benchmark evidence by itself.
