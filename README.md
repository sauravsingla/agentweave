# AgentWeave — Route Before You Reason

[![CI](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml)
[![A2A SDK Interop](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml)
[![Deep Proof](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml)
[![Paper Quality](https://github.com/sauravsingla/agentweave/actions/workflows/paper-quality.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/paper-quality.yml)

AgentWeave is an open-source routing and reliability layer for tool-rich and multi-agent systems. It reduces the tool or agent set exposed to a model before inference, while keeping policy, provenance, recovery, and downstream execution explicit.

```text
large tool / agent catalog
          ↓
 policy + capability checks
          ↓
   AgentWeave routing
          ↓
 smaller model-visible set
          ↓
   existing model
          ↓
 execution + verification
```

Use deterministic scope reduction first when role, tenant, permission, or policy already narrows the catalog sufficiently. Add task-aware routing only when the remaining action space still needs it.

## Start here

| Use case | Guide |
|---|---|
| MCP tool-rich agents | [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md) |
| LangGraph workflows | [`docs/LANGGRAPH_INTEGRATION.md`](docs/LANGGRAPH_INTEGRATION.md) |
| AutoGen teams | [`docs/AUTOGEN_INTEGRATION.md`](docs/AUTOGEN_INTEGRATION.md) |
| A2A interoperable agents | [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md) |
| BFCL-derived evaluation | [`docs/BFCL_REPRODUCE.md`](docs/BFCL_REPRODUCE.md) |
| API compatibility | [`docs/API_COMPATIBILITY.md`](docs/API_COMPATIBILITY.md) |

## Core capabilities

- Pre-inference routing and requirement-aware selection
- Policy, placement, trust, and provenance controls
- Multi-agent team optimization
- A2A interoperability and external SDK compatibility
- Runtime recovery, re-ranking, and failover
- Durable workflows with checkpoint/resume
- Verification, consensus, observability, and auditability

## Quick start

```bash
git clone https://github.com/sauravsingla/agentweave.git
cd agentweave
python -m pip install -e '.[dev]'
pytest -q
```

Minimal example:

```python
import asyncio
from agentweave import AgentWeave, AgentProfile, Capability, InMemoryA2AAdapter

async def main():
    bus = InMemoryA2AAdapter()
    weave = AgentWeave(a2a=bus, db_path=':memory:')

    agent = AgentProfile(
        'research-1',
        'Research Agent',
        [Capability('research', .9, True)],
    )

    weave.register(agent)
    bus.register_handler(
        'research-1',
        lambda task: {'result': 'evidence-backed finding'},
    )

    result = await weave.solve(
        'Research and verify this topic',
        rounds=1,
        semantic_verify=True,
    )
    print(result)

asyncio.run(main())
```

Useful CLI commands:

```bash
agentweave version
agentweave doctor
agentweave graph-stats
agentweave plugins
agentweave --config agentweave.yaml config-check
agentweave solve --semantic-verify "Research and verify this topic"
```

Optional integrations:

```bash
python -m pip install -e '.[security,api,tck,grpc,native,postgres,aws,observability,edge,yaml,ontology]'
```

## Integration model

AgentWeave sits before downstream model or agent execution rather than replacing existing frameworks.

### MCP

```text
MCP tools → policy/capability filtering → AgentWeave routing → model-visible tools
```

### LangGraph

```text
LangGraph state → AgentWeave routing node → selected specialists → downstream nodes
```

### AutoGen

```text
task → AgentWeave routing → selected participants → AutoGen execution
```

### A2A

AgentWeave treats A2A as the communication substrate. The proof suite launches independent upstream A2A SDK agents and exercises discovery and invocation across Python, Go, JavaScript, and Java.

**Current proof:** JSON-RPC MUST-level TCK.

See [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md).

## Architecture

```text
Discovery
   ↓
Registry
   ↓
Identity / Security / Policy
   ↓
Requirement Intelligence
   ↓
Capability + Knowledge Matching
   ↓
Contextual Trust + Placement
   ↓
Team Optimization
   ↓
A2A / Tool Execution
   ↓
Failure Detection + Recovery
   ↓
Verification + Observability
```

## Research evidence

AgentWeave keeps routing, process-verification, executable-outcome, and BFCL-derived evidence separate rather than combining unlike metrics into one score.

| Evidence | Evaluation problem | Current result |
|---|---|---|
| **AgentBench** | Blind specialist selection | **52.0% Hit@1**; **89.9% accuracy on committed routes** at **46.3% coverage** |
| **ToolBench** | Tool/API retrieval over 4,856 APIs | **35.8% Hit@1**, **47.5% Hit@3**, **53.8% Hit@5**, MRR **0.440** |
| **AgencyBench** | Capability-family routing | **57.0% zero-shot Hit@1**; **67.2% cumulative-context Hit@1**; **92.2% cumulative-context Hit@3** |
| **AgentProcessBench** | Label-blind process verification | **55.88% step micro accuracy**; **38.30% first-error accuracy** across **1,000 trajectories / 8,509 steps** |
| **BFCL routing-pressure v6** | Native BFCL validity under augmented tool pressure | **6/48 = 12.5% AgentWeave vs 0/48 for all matched baselines**, exact McNemar **p = 0.03125** |
| **Executable team benchmark** | Controlled multi-agent completion and recovery | **100% completion**, **0.937 mean quality**, **100% recovery** in the preregistered repeated-seed study |

### BFCL-derived routing-pressure study

The v6 study uses 48 fresh BFCL V4 `multiple` tasks, a pinned local `MadeAgents/Hammer2.1-1.5b` model, 16-tool pressure, and matched all-tools, random-top-8, semantic-top-8, and AgentWeave conditions.

AgentWeave achieved **6/48 = 12.5%** native successes versus **0/48** for each matched baseline. The paired advantage is **+12.5 percentage points**, with a **10,000-resample paired bootstrap 95% CI of +4.17 to +22.92 pp** and exact McNemar **p = 0.03125**.

Relative to all-tools, AgentWeave exposed **70.18% fewer tools**, used **61.70% fewer input tokens**, and showed **50.95% lower mean local-model latency**.

**Boundary:** this is a BFCL-derived routing-pressure study, not an official full BFCL leaderboard score.

Reproduction and frozen results:

- [`BFCL_V5_RESULTS.md`](BFCL_V5_RESULTS.md)
- [`BFCL_V6_RESULTS.md`](BFCL_V6_RESULTS.md)
- [`docs/BFCL_REPRODUCE.md`](docs/BFCL_REPRODUCE.md)
- [`evaluation/bfcl-routing-pressure-v6-frozen.json`](evaluation/bfcl-routing-pressure-v6-frozen.json)

### Frozen-router generalization

AgentWeave evaluates new router versions on newly introduced untouched holdouts, then freezes those results. Percentages across rows are not directly comparable; the valid comparison is the previous router versus the new router on the same new holdout.

| Evaluation | Tasks | Same-holdout result |
|---|---:|---:|
| Frozen original router | 499 | **15.6% Hit@1**; majority baseline 39.9% |
| Router V2 | 72 | 52.8% → **54.2% Hit@1** |
| Router V3 | 72 | 31.9% → **76.4% Hit@1** |
| Router V4 | 72 | 72.2% → **91.7% Hit@1** |
| Router V5 | 72 | 38.9% → **77.8% interactive Hit@1** |
| Router V6 | 72 | 37.5% → **59.7% interactive Hit@1** |
| Router V7 | 72 | 73.6% → **91.7% search-family Hit@1** |

## Scientific boundaries

- Scored studies are frozen after scoring.
- Weak and negative results are retained.
- New router versions use newly introduced holdouts.
- BFCL-derived evidence is not described as an official BFCL leaderboard result.
- Controlled synthetic execution is not described as production performance.
- Routing accuracy is not presented as native task completion.
- Changes to model, sample, router, distractors, or protocol require a new study.

The paper-quality evaluation also retains the post-hoc result that simple zero-shot embedding baselines outperform the original frozen AgentWeave router on the already-observed General-AgentBench set.

## Reliability, security, and scale

AgentWeave supports failure detection, trust updates, re-ranking, replacement selection, retry, and durable checkpoint/resume workflows.

The proof suite covers malicious Agent Cards, prompt injection, data exfiltration, SSRF/link-local access, tool abuse, spoofing, Sybil/collusion, reputation poisoning, Byzantine disagreement, malformed results, and timeouts. It also exercises Docker isolation, JWT Verifiable Credentials, revocation, key rotation, KMS/HSM boundaries, PostgreSQL concurrency, governance constraints, and chaos scenarios.

A passing proof is evidence for the configured test runtime; it is not a formal security, HA, hardware-attestation, or compliance certification.

Synthetic scalability runs extend to **1,000,000 agents**. Negative measurements are preserved as part of the evidence record.

## Current design work

- [Issue #22 — make tool-routing provenance explicit](https://github.com/sauravsingla/agentweave/issues/22)
- [Issue #27 — policy-first static scope filtering before dynamic tool routing](https://github.com/sauravsingla/agentweave/issues/27)
- [Issue #29 — stage-specific failure analysis and recovery stress tests](https://github.com/sauravsingla/agentweave/issues/29)

## Contributing

External reproductions, interoperability reports, integrations, benchmark scenarios, security tests, and documentation improvements are welcome.

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), [`CHANGELOG.md`](CHANGELOG.md), and [`CITATION.cff`](CITATION.cff).

## Paper

**AgentWeave: Routing Before Reasoning for Efficient Function Calling in Tool-Rich Language Models**  
[arXiv:2608.23078](https://arxiv.org/abs/2608.23078) · [`PAPER.md`](PAPER.md)

## License

Apache-2.0
