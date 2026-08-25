# Issue #29 Recovery and State-Change Stress Evaluation

This document describes the controlled evaluation added for the remaining recovery-focused acceptance criteria in Issue #29.

## Scope

The harness compares three conditions without modifying the frozen AgentWeave runtime or historical BFCL-derived scores:

1. **Fixed routed set** — the initially selected capability set is frozen and cannot expand.
2. **Re-route on failure/state change** — the system may perform one controlled re-routing step when the selected tool fails or a new capability becomes necessary.
3. **All-tools exposure** — all available capabilities are visible from the start.

## Controlled scenarios

### Selected tool failure

The initially selected capability fails unexpectedly. Recovery requires a fallback capability that was not in the initial routed set.

Expected controlled outcome:

- fixed routed set: fails;
- re-routing: succeeds after one re-routing event;
- all-tools: succeeds because the fallback capability is already visible.

### State change requiring a new capability

The task begins with a `lookup` capability. An intermediate state change makes `verify` necessary, although `verify` was not initially selected.

Expected controlled outcome:

- fixed routed set: the new capability does not survive and the task fails;
- re-routing: the capability is added and the task succeeds;
- all-tools: the capability was already visible and the task succeeds.

## Metrics

Each condition records independently:

- required-tool survival before and after state change;
- number of re-routing events;
- recovery success;
- extra model calls;
- extra tool calls;
- latency overhead;
- token overhead;
- final task success.

The deterministic harness is implemented in [`evaluation/recovery_stress.py`](../evaluation/recovery_stress.py), with regression coverage in [`tests/test_recovery_stress.py`](../tests/test_recovery_stress.py).

## Evidence boundary

This is a controlled stress-test harness for evaluating recovery behavior. It is not a new BFCL score, does not rewrite any frozen benchmark artifact, and should not be interpreted as production reliability evidence. Its purpose is to make the trade-off between narrow initial exposure and recovery overhead measurable under explicit state changes and tool failures.
