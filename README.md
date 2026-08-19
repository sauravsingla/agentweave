# AgentWeave — Route Before You Reason

[![CI](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml)
[![A2A SDK Interop](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml)
[![Deep Proof](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml)
[![Paper Quality](https://github.com/sauravsingla/agentweave/actions/workflows/paper-quality.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/paper-quality.yml)

**AgentWeave reduces the tool/agent set before inference so a model sees a smaller, more relevant action space — without changing the underlying model.**

Use it as a routing and reliability layer around **MCP tool catalogs, A2A agents, LangGraph workflows, AutoGen teams, enterprise catalogs, marketplaces, cloud agents, and edge runtimes**.

```text
large tool / agent catalog
          ↓
 policy + capability checks
          ↓
   AgentWeave routing
          ↓
 smaller model-visible set
          ↓
   your existing model
          ↓
 execution + verification
```

**Why this matters:** when a system exposes many heterogeneous tools or agents, the model has to reason over a larger action space. AgentWeave moves part of that decision into a reproducible pre-inference layer and keeps selection, policy, trust, recovery, and provenance explicit.

> **Routing is optional, not dogmatic.** If deterministic role, tenant, permission, or policy scope already reduces the catalog enough, use that first. Add task-aware routing only when the remaining action space still needs it.

## Start here

| If you are building... | Start with... |
|---|---|
| MCP tool-rich agents | [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md) |
| LangGraph workflows | [`docs/LANGGRAPH_INTEGRATION.md`](docs/LANGGRAPH_INTEGRATION.md) |
| AutoGen teams | [`docs/AUTOGEN_INTEGRATION.md`](docs/AUTOGEN_INTEGRATION.md) |
| A2A interoperable agents | [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md) |
| Reproducible BFCL-derived evaluation | [`docs/BFCL_REPRODUCE.md`](docs/BFCL_REPRODUCE.md) |
| API / compatibility details | [`docs/API_COMPATIBILITY.md`](docs/API_COMPATIBILITY.md) |

## What AgentWeave adds

Agent interoperability answers **how agents communicate**. AgentWeave focuses on **which tools/agents should be visible or selected, whether they satisfy policy and trust constraints, where they should execute, how teams should be formed, and what happens when execution fails**.

Core capabilities include:

- **Pre-inference routing:** construct a smaller model-visible action space before the model call.
- **Requirement-aware selection:** infer task capabilities and rank matching agents/tools.
- **Policy and placement:** scopes, jurisdiction, residency, locality, risk tiers, human approval, and tool restrictions.
- **Contextual trust:** identity, validation, freshness, historical outcomes, governance, and reputation.
- **Global team optimization:** capability coverage, redundancy, diversity, cost, latency, and communication overhead.
- **A2A interoperability:** Agent Cards, JSON-RPC, HTTP+JSON, streaming, push notifications, subscription, retry/resume, and gRPC lifecycle calls.
- **Runtime recovery:** detect failure, update trust, re-rank alternatives, and fail over automatically.
- **Durable workflows:** checkpoint multi-step work and resume without replaying completed steps.
- **Verification and consensus:** contradiction, uncertainty, semantic verification, result validation, and conflict handling.
- **Observability and auditability:** structured traces, audit events, metrics, and explicit selection evidence.

## Quick start

Install from source:

```bash
git clone https://github.com/sauravsingla/agentweave.git
cd agentweave
python -m pip install -e '.[dev]'
pytest -q
```

Minimal A2A example:

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

## Integration boundaries

### MCP

AgentWeave can sit between an MCP tool catalog and the model-facing tool list:

```text
MCP tools
   ↓
policy / capability filtering
   ↓
AgentWeave routing
   ↓
smaller model-visible tool set
   ↓
normal model execution
```

See [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md).

### LangGraph

```text
LangGraph state
      ↓
AgentWeave routing node
      ↓
selected specialists + explanation
      ↓
normal downstream LangGraph nodes
```

See [`docs/LANGGRAPH_INTEGRATION.md`](docs/LANGGRAPH_INTEGRATION.md).

### AutoGen

```text
task
 ↓
AgentWeave routing
 ↓
selected AutoGen participants
 ↓
normal AutoGen team execution
```

See [`docs/AUTOGEN_INTEGRATION.md`](docs/AUTOGEN_INTEGRATION.md).

### A2A

AgentWeave treats A2A as the communication substrate rather than replacing it. Independent upstream A2A SDK agents are launched and invoked in GitHub Actions.

| SDK | Discovery | Invocation |
|---|---:|---:|
| Python | ✅ | ✅ |
| Go | ✅ | ✅ |
| JavaScript | ✅ | ✅ |
| Java | ✅ | ✅ |

The proof suite also runs the official A2A TCK against AgentWeave as the system under test.

**Current proof:** ✅ JSON-RPC MUST-level TCK.

See [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md).

## Architecture

```text
Cloud / Marketplace / Enterprise / Edge Agents
                    │
              Agent Discovery
                    │
              Agent Registry
                    │
      Identity / Security / Policy
                    │
        Requirement Intelligence
      lexical → semantic → optional LLM
                    │
     Capability + Knowledge Ontology
                    │
            Contextual Trust
                    │
        Matching + Placement
                    │
        Global Team Optimizer
                    │
                   A2A
                    │
      Runtime Failure Detection
                    │
       Trust Update + Re-ranking
                    │
      Replacement Agent / Team
                    │
      Durable Checkpoint / Resume
                    │
   Consensus + Conflict Resolution
                    │
     Result + Semantic Verification
                    │
      Reputation + Dynamic Retesting
```

## Research evidence

AgentWeave deliberately separates **routing/selection evidence**, **process-verification evidence**, **controlled executable outcomes**, and **BFCL-derived function-calling evidence** rather than presenting unlike measurements as one leaderboard.

| Evidence | Evaluation problem | Current result |
|---|---|---|
| **AgentBench** | Blind specialist selection | **52.0% Hit@1**; **89.9% accuracy on committed routes** at **46.3% coverage** |
| **ToolBench** | Tool/API retrieval over 4,856 APIs | **35.8% Hit@1**, **47.5% Hit@3**, **53.8% Hit@5**, MRR **0.440** |
| **AgencyBench** | Capability-family routing | **57.0% zero-shot Hit@1**; **67.2% cumulative-context Hit@1**; **92.2% cumulative-context Hit@3** |
| **AgentProcessBench** | Label-blind process verification | **55.88% step micro accuracy**; **38.30% first-error accuracy** across **1,000 trajectories / 8,509 steps** |
| **BFCL routing-pressure v6** | Native BFCL validity under augmented tool pressure | **6/48 = 12.5% AgentWeave vs 0/48 for all three matched baselines**, exact McNemar **p = 0.03125** |
| **Executable team benchmark** | Controlled multi-agent completion and recovery | **100% completion**, **0.937 mean quality**, **100% recovery** in the preregistered repeated-seed study |

### BFCL-derived routing-pressure replication

The v6 study uses 48 fresh BFCL V4 `multiple` tasks, a pinned local `MadeAgents/Hammer2.1-1.5b` model, 16-tool pressure, and matched all-tools, random-top-8, semantic-top-8, and AgentWeave conditions.

| Study | Fresh tasks | AgentWeave | All-tools | Random top-8 | Semantic top-8 |
|---|---:|---:|---:|---:|---:|
| **V5 pilot** | 12 | **2/12 = 16.67%** | 0/12 | 0/12 | 0/12 |
| **V6 replication** | 48 | **6/48 = 12.5%** | 0/48 | 0/48 | 0/48 |

For v6, the paired AgentWeave advantage versus each matched baseline is **+12.5 percentage points**, with a **10,000-resample paired bootstrap 95% CI of +4.17 to +22.92 pp** and exact McNemar **p = 0.03125**. Relative to all-tools, AgentWeave exposes **70.18% fewer tools**, uses **61.70% fewer input tokens**, and shows **50.95% lower mean local-model latency**.

**Important boundary:** this is a **BFCL-derived routing-pressure study, not an official full BFCL leaderboard score**.

Results and reproduction:

- [`BFCL_V5_RESULTS.md`](BFCL_V5_RESULTS.md)
- [`BFCL_V6_RESULTS.md`](BFCL_V6_RESULTS.md)
- [`docs/BFCL_REPRODUCE.md`](docs/BFCL_REPRODUCE.md)
- [`evaluation/bfcl-routing-pressure-v5-frozen.json`](evaluation/bfcl-routing-pressure-v5-frozen.json)
- [`evaluation/bfcl-routing-pressure-v6-frozen.json`](evaluation/bfcl-routing-pressure-v6-frozen.json)

### Frozen-router generalization

AgentWeave maintains a sequence of newly introduced untouched holdouts. Each router version is scored once on its new holdout and then frozen.

| Evaluation | Tasks | Same-holdout result |
|---|---:|---:|
| Frozen original router | 499 | **15.6% Hit@1**; majority baseline 39.9% |
| Router V2 | 72 | 52.8% → **54.2% Hit@1** |
| Router V3 | 72 | 31.9% → **76.4% Hit@1** |
| Router V4 | 72 | 72.2% → **91.7% Hit@1** |
| Router V5 | 72 | 38.9% → **77.8% interactive Hit@1** |
| Router V6 | 72 | 37.5% → **59.7% interactive Hit@1** |
| Router V7 | 72 | 73.6% → **91.7% search-family Hit@1** |

These rows use different holdouts. The valid comparison is the previous router versus the new router on the **same newly introduced holdout**, not percentages across rows.

## Reproducibility and scientific boundaries

The repository keeps research claims deliberately narrow:

- scored studies are frozen after scoring;
- weak and negative results are retained;
- newly introduced holdouts are used for later router versions;
- paired bootstrap intervals and exact McNemar tests are reported where appropriate;
- BFCL-derived routing-pressure evidence is not described as an official BFCL leaderboard result;
- controlled synthetic execution is not described as production performance;
- routing accuracy is not presented as native task completion;
- changes to model, sample, router, distractors, or protocol require a new study rather than rewriting frozen evidence.

The paper-quality evaluation also preserves the post-hoc result that simple zero-shot embedding baselines outperform the original frozen AgentWeave router on the already-observed General-AgentBench set.

## Runtime recovery and durable workflows

When a selected agent fails, AgentWeave can update trust, re-rank remaining candidates, choose a replacement, and continue execution.

```text
requirement
   ↓
select Agent A
   ↓
Agent A fails
   ↓
trust update + re-ranking
   ↓
select Agent B
   ↓
retry / continue
   ↓
validate final outcome
```

`DurableAgentWeave` checkpoints completed workflow steps and can resume from the next unfinished step. Persistence paths include SQLite, PostgreSQL, and replicated storage.

## Security and governance

The proof suite covers malicious Agent Cards, prompt injection, data exfiltration, SSRF/link-local access, tool abuse, spoofing, Sybil/collusion, reputation poisoning, Byzantine disagreement, malformed results, and timeouts.

It also exercises Docker isolation, JWT Verifiable Credentials, revocation, certificate/key rotation, KMS/HSM integration boundaries, PostgreSQL concurrency and reconnect behavior, governance constraints, and chaos scenarios.

A passing proof is evidence for the configured test runtime; it is **not** a formal security, HA, hardware-attestation, or compliance certification.

## Scalability

A physical GitHub Actions run evaluated synthetic populations up to 1,000,000 agents. The repository reports both positive and negative measurements; notably, the current native C++ ranking path is slower than Python in that benchmark and is reported as such.

## Paper

A research preprint is in preparation under the working title:

**AgentWeave: Routing Before Reasoning for Efficient Function Calling in Tool-Rich LLM Agents**

Until an archival paper is published, research users should cite the software using [`CITATION.cff`](CITATION.cff). No arXiv identifier or DOI is claimed yet.

## Current design work

Two active design questions are tracked publicly:

- [Issue #22 — make tool-routing provenance explicit](https://github.com/sauravsingla/agentweave/issues/22)
- [Issue #27 — policy-first static scope filtering before dynamic tool routing](https://github.com/sauravsingla/agentweave/issues/27)

The intended direction is:

```text
source catalog
    ↓
authorization / deterministic scope
    ↓
optional task-aware routing
    ↓
final model-visible capability set
```

The portable evidence should describe **what transformations produced the model-visible set**, not expose private reasoning traces.

## Contributing

External reproductions, interoperability reports, integrations, benchmark scenarios, security tests, documentation improvements, and real-world evaluation datasets are especially welcome.

- **Issues:** use GitHub Issues.
- **Pull requests:** see [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Compatibility:** see [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md).
- **Security:** see [`SECURITY.md`](SECURITY.md).

## Release and compatibility

AgentWeave follows Semantic Versioning. See [`CHANGELOG.md`](CHANGELOG.md), [`docs/API_COMPATIBILITY.md`](docs/API_COMPATIBILITY.md), and [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md).

## About

AgentWeave is an open-source project by **Saurav Singla** for research and engineering around pre-inference routing and interoperable, trustworthy, failure-aware multi-agent orchestration.

## License

Apache-2.0
