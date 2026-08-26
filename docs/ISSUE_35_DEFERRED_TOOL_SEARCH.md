# Issue #35 — Deferred Tool Search / Progressive Disclosure

This evaluation compares four tool-disclosure strategies:

1. all tools visible;
2. policy-only reduction;
3. policy + task-aware routing;
4. policy + routing + deferred tool search on miss/recovery.

The design goal is to test when progressive disclosure is beneficial and when it merely adds search/model round trips.

## Flow

```text
source catalog
  -> deterministic scope/policy filter
  -> optional task-aware routing
  -> model-visible tools
  -> if required capability is missing: deferred tool search
  -> newly disclosed candidate(s)
  -> authorization boundary
  -> execution / recovery
```

Deferred search never bypasses deterministic policy. A tool excluded by policy cannot be added to the model-visible set through discovery.

## Controlled scenarios

The benchmark includes:

- policy filtering already preserves the required tool;
- routing misses a required tool and deferred search restores it;
- a state change introduces a newly required fallback capability;
- an unnecessary-search case where a valid visible tool already exists;
- a hidden unauthorized/malicious tool that must remain non-executable;
- a large noisy catalog that stresses initial context size.

## Metrics

Each condition reports:

- end-to-end task success;
- initial and final model-visible tool counts;
- deferred-search invocation count;
- unnecessary-search count;
- extra model round trips and tool calls;
- input-token proxy;
- routing, search, model, and total latency proxies;
- unauthorized discovery attempts;
- unauthorized executions;
- recovery success;
- candidate-set reduction.

## Interpretation

The benchmark is designed to expose three distinct outcomes:

- **policy is sufficient:** dynamic routing/search can be unnecessary overhead;
- **routing is useful:** it reduces initial context when the required tool survives;
- **deferred search is useful:** it restores success after a routing miss or state change, but its additional round trips should be counted explicitly.

The unauthorized-hidden scenario tests the security boundary: discovery may attempt to find a denied capability, but policy prevents it from becoming model-visible or executable.

## Evidence boundary

This is a controlled deterministic architectural comparison. Token and latency values are modeled proxies, not production measurements. The benchmark does not claim provider-level tool-search performance or production security guarantees.

Existing frozen BFCL-derived results and historical router artifacts are not modified by this work.
