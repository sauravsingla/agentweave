# AgentWeave

[![CI](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml)
[![A2A SDK Interop](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml)
[![Deep Proof](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml)
[![Paper Quality](https://github.com/sauravsingla/agentweave/actions/workflows/paper-quality.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/paper-quality.yml)

**Knowledge-, capability-, trust-, policy-, and confidence-aware orchestration for heterogeneous AI agents.**

AgentWeave is an open-source framework for discovering, validating, selecting, and orchestrating AI agents across cloud, marketplaces, enterprise environments, and edge devices. It uses **A2A as the interoperability layer** and adds requirement intelligence, contextual trust, capability and knowledge reasoning, placement and team optimization, governance, result verification, reputation learning, observability, automatic runtime failover, and durable workflow recovery.

> **A2A answers:** how can agents communicate?
>
> **AgentWeave adds:** which agents should communicate for a requirement, whether they can be trusted, where they should execute, how teams should be formed, what should happen when a selected agent fails, how work should resume, and how outputs should be validated and learned from.

With AgentWeave, applications can:

- discover agents through A2A Agent Cards, registries, marketplaces, enterprise catalogs, and edge runtimes;
- infer structured requirements from raw task text with explicit confidence and ambiguity;
- validate identity, capability, security, policy, freshness, and historical evidence;
- rank agents using capability, domain, knowledge, trust, placement, cost, and latency;
- form multi-agent teams across coverage, trust, diversity, redundancy, cost, and communication overhead;
- orchestrate A2A lifecycle operations, streaming, cancellation, subscription, retry, and resume;
- detect runtime failures, update trust, re-rank alternatives, and automatically fail over;
- persist multi-step workflow checkpoints and resume without replaying completed steps;
- verify outputs with contradiction, citation/source-quality, uncertainty, consensus, and verifier hooks;
- learn from outcomes through persistent reputation and dynamic re-testing.

## Why AgentWeave?

Agent interoperability alone does not solve agent selection. Real agent ecosystems contain heterogeneous agents with different expertise, trust, costs, latency, execution locations, security boundaries, and implementation stacks.

AgentWeave is designed to add a **decision and reliability layer above interoperability**:

- **Requirement-aware selection:** infer what the task actually needs before choosing an agent.
- **Trust-aware orchestration:** combine capability with validation, reputation, policy, and contextual trust.
- **Global team formation:** select a set of agents that collectively covers the requirement rather than greedily choosing one candidate at a time.
- **Failure-aware execution:** update trust after real runtime failures and select replacements automatically.
- **Durable workflows:** checkpoint multi-step progress and resume after restart.
- **Evidence-aware verification:** validate outputs and preserve confidence, disagreement, and failure evidence.
- **Research-grade evaluation:** preserve weak results, freeze scored experiments, use untouched holdouts, and report statistical uncertainty.

### Key features

- **A2A-native interoperability:** Agent Card discovery, JSON-RPC and HTTP+JSON lifecycle operations, streaming, push notifications, subscription, retry/resume, and generated-stub gRPC lifecycle calls.
- **Requirement intelligence:** deterministic lexical signals, generic semantic inference, confidence, ambiguity metadata, and optional semantic/LLM fallback.
- **Capability and knowledge modeling:** ontology-backed capability and domain reasoning.
- **Contextual trust:** identity, validation, freshness, historical outcomes, governance constraints, and reputation.
- **Placement and policy:** locality, residency, scopes, jurisdiction, risk tiers, human approval, and tool restrictions.
- **Global team optimization:** coverage, redundancy, trust, diversity, latency, cost, and communication overhead.
- **Runtime recovery:** automatic failure detection, trust update, re-ranking, replacement, and repeated failover.
- **Durable checkpointing:** SQLite, PostgreSQL, and replicated persistence paths for multi-step workflows.
- **Verification and consensus:** contradiction, uncertainty, semantic verification, result validation, consensus, and conflict handling.
- **Security and observability:** sandboxing, auditability, malicious Agent Card defenses, SSRF protections, identity controls, and chaos testing.

## Getting started

### Install from source

```bash
python -m pip install -e '.[dev]'
pytest -q
```

Optional integrations:

```bash
python -m pip install -e '.[security,api,tck,grpc,native,postgres,aws,observability,edge,yaml,ontology]'
```

### Minimal example

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
    bus.register_handler('research-1', lambda task: {'result': 'evidence-backed finding'})

    result = await weave.solve(
        'Research and verify this topic',
        rounds=1,
        semantic_verify=True,
    )
    print(result)

asyncio.run(main())
```

### CLI

```bash
agentweave version
agentweave doctor
agentweave graph-stats
agentweave plugins
agentweave --config agentweave.yaml config-check
agentweave solve --semantic-verify "Research and verify this topic"
```

## Architecture

```text
Cloud / Marketplace / Enterprise / Edge Agents
                    │
              Agent Discovery
                    │
              Agent Registry
                    │
      Identity / Security / Benchmarks
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

## A2A interoperability

AgentWeave treats A2A as the communication substrate rather than replacing it. The framework supports Agent Card discovery, task lifecycle operations, streaming, task lookup/list/cancel, subscription, retry/resume, push-notification configuration, and authenticated push reception.

### Cross-SDK proof

Independent upstream A2A SDK agents are launched and invoked in GitHub Actions:

| SDK | Discovery | Invocation |
|---|---:|---:|
| Python | ✅ | ✅ |
| Go | ✅ | ✅ |
| JavaScript | ✅ | ✅ |
| Java | ✅ | ✅ |

### Public interoperability proof

| Service | Discovery | Real invocation |
|---|---:|---:|
| Deep Research Archives | ✅ | ✅ |
| Delx Agent Operations Protocol | ✅ | ✅ |

The Deep Proof workflow also executes the official A2A TCK against AgentWeave as the system under test.

```bash
uv run ./run_tck.py --sut-host http://127.0.0.1:9998 --transport jsonrpc --level must
```

**Current proof:** ✅ JSON-RPC MUST-level TCK.

See [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md) for the tested compatibility boundary and SDK version policy.

## Paper

A research preprint is in preparation under the working title:

**AgentWeave: Routing Before Reasoning for Efficient Function Calling in Tool-Rich LLM Agents**

The manuscript is intended to document the routing problem, AgentWeave's pre-inference selection methodology, frozen experiments and statistical analysis, limitations, reproducibility controls, and the path toward standard BFCL evaluation. It will explicitly separate BFCL-derived routing-pressure evidence from any future official BFCL leaderboard result.

Planned coverage includes:

- capability/provider-aware pre-inference routing and bounded model-visible tool sets;
- controlled same-model comparisons that isolate orchestration effects from model scaling;
- frozen BFCL-derived routing-pressure studies and paired statistical analysis;
- efficiency measurements including model-visible tools, input tokens, and latency;
- failure analysis, including missing-tool, schema-competition, and multi-function completeness failures;
- evidence boundaries, limitations, and independent-reproduction requirements;
- BFCL-compatible integration for standard benchmark-native evaluation.

**Status:** manuscript in preparation; no arXiv identifier or DOI is claimed yet. Until a preprint is published, research users should cite the software release using [`CITATION.cff`](CITATION.cff). Once an archival paper is available, this section and the citation metadata will be updated with the canonical paper identifier.

## Research and benchmark evidence

AgentWeave separates **routing/selection evidence**, **process-verification evidence**, **controlled executable outcomes**, and **BFCL-derived native function-calling evidence** rather than presenting unlike measurements as a single leaderboard.

### Evidence at a glance

| Evidence | Evaluation problem | Current result |
|---|---|---|
| **AgentBench** | Blind specialist selection | **52.0% Hit@1**; **89.9% accuracy on committed routes** at **46.3% coverage** |
| **ToolBench** | Tool/API retrieval over 4,856 APIs | **35.8% Hit@1**, **47.5% Hit@3**, **53.8% Hit@5**, MRR **0.440** |
| **AgencyBench** | Capability-family routing | **57.0% zero-shot Hit@1**; **67.2% cumulative-context Hit@1**; **92.2% cumulative-context Hit@3** |
| **AgentProcessBench** | Label-blind process verification | **55.88% step micro accuracy**; **38.30% first-error accuracy** across **1,000 trajectories / 8,509 steps** |
| **BFCL routing-pressure v6** | Native BFCL validity under augmented tool pressure | **6/48 = 12.5% AgentWeave vs 0/48 for all three matched baselines**, exact McNemar **p = 0.03125** |
| **Executable team benchmark** | Controlled multi-agent completion and recovery | **100% completion**, **0.937 mean quality**, **100% recovery** across the preregistered repeated-seed study |
| **Frozen-router holdouts** | Untouched routing-transfer tests | Router V2–V7 each scored once on a newly introduced holdout; improvements are valid only within each same-holdout comparison |

These measurements are intentionally scoped. AgentBench, ToolBench, AgencyBench, and the frozen-router holdouts are routing/selection evaluations; AgentProcessBench is process verification; the controlled team benchmark executes synthetic workload handlers; and the BFCL study uses native BFCL evaluation under a custom routing-pressure setup.

### BFCL routing-pressure replication

AgentWeave maintains a separate **BFCL-derived routing-pressure study** that preserves untouched BFCL questions and native BFCL evaluation while deterministically expanding model-visible tool context. It is **not an official full BFCL leaderboard score**.

The frozen v5 pilot and untouched v6 replication use the same pinned BFCL/Gorilla commit, the same local keyless `MadeAgents/Hammer2.1-1.5b` model, the same 16-tool pressure, the same all-tools/random-top-8/semantic-top-8 baselines, and the same AgentWeave 4-provider / 6-tool budget. V6 excludes every v5 task.

| Study | Fresh tasks | AgentWeave | All-tools | Random top-8 | Semantic top-8 | Exact McNemar vs each baseline |
|---|---:|---:|---:|---:|---:|---:|
| **V5 pilot** | 12 | **2/12 = 16.67%** | 0/12 | 0/12 | 0/12 | `p = 0.5` |
| **V6 replication** | 48 | **6/48 = 12.5%** | 0/48 | 0/48 | 0/48 | **`p = 0.03125`** |

For v6, the paired AgentWeave advantage versus each matched baseline is **+12.5 percentage points**, with a **10,000-resample paired bootstrap 95% CI of +4.17 to +22.92 pp**. Relative to all-tools, AgentWeave exposes **70.18% fewer tools**, uses **61.70% fewer input tokens**, and shows **50.95% lower mean local-model latency**.

See [`BFCL_V5_RESULTS.md`](BFCL_V5_RESULTS.md), [`BFCL_V6_RESULTS.md`](BFCL_V6_RESULTS.md), [`evaluation/bfcl-routing-pressure-v5-frozen.json`](evaluation/bfcl-routing-pressure-v5-frozen.json), and [`evaluation/bfcl-routing-pressure-v6-frozen.json`](evaluation/bfcl-routing-pressure-v6-frozen.json).

### Frozen-router generalization

AgentWeave maintains a frozen-router sequence to test whether routing improvements transfer beyond data already inspected during development. Each router version is scored once on a newly preregistered external holdout, then frozen.

| Evaluation | New untouched holdout | Tasks | Same-holdout result |
|---|---|---:|---:|
| Frozen original router | General-AgentBench | 499 | **15.6% Hit@1**; majority baseline 39.9% |
| Router V2 | GSM8K + HumanEval + InterCode NL2Bash | 72 | 52.8% → **54.2% Hit@1** |
| Router V3 | MBPP + TruthfulQA + OSWorld | 72 | 31.9% → **76.4% Hit@1** |
| Router V4 | CRUXEval + BrowserGym MiniWoB + WorkArena | 72 | 72.2% → **91.7% Hit@1** |
| Router V5 | VisualWebArena | 72 | 38.9% → **77.8% interactive Hit@1** |
| Router V6 | WebArena | 72 | 37.5% → **59.7% interactive Hit@1** |
| Router V7 | AssistantBench | 72 | 73.6% → **91.7% search-family Hit@1** |

**Comparison rule:** these rows use different holdouts. The scientifically valid comparison is the previous router versus the new router on the **same newly introduced holdout**, not the percentages across different rows.

The weak original General-AgentBench result is intentionally retained. Later routers live under `research/` rather than silently replacing that evidence.

### Research-quality controls

The repository applies explicit controls intended to reduce overfitting and evidence inflation:

- preregistered hypotheses where the study is confirmatory;
- deterministic content-blind sampling rules;
- frozen scored experiments and immutable weak/negative results;
- newly introduced untouched holdouts for later router versions;
- Wilson confidence intervals, paired bootstrap intervals, and exact McNemar tests where appropriate;
- failure and disagreement rows retained in evidence artifacts;
- strong semantic baselines reported even when they outperform the original frozen router;
- explicit boundaries between routing metrics, native benchmark outcomes, controlled synthetic outcomes, and production claims.

The paper-quality evaluation also reports that simple zero-shot embedding baselines outperform the original frozen AgentWeave router on the already-observed General-AgentBench set. That result is preserved as exploratory/post-hoc evidence rather than hidden.

Reproduce or inspect the research-quality proof through [`.github/workflows/paper-quality.yml`](.github/workflows/paper-quality.yml), [`scripts/paper_semantic_baselines.py`](scripts/paper_semantic_baselines.py), and [`scripts/paper_outcome_evaluation.py`](scripts/paper_outcome_evaluation.py).

## Runtime failover and durable workflows

AgentWeave supports a closed-loop recovery path when a selected agent fails during execution:

```text
requirement
   ↓
discover + rank candidates
   ↓
select Agent A
   ↓
Agent A fails
   ↓
negative trust/reputation update
   ↓
re-rank remaining candidates
   ↓
select Agent B
   ↓
retry / continue with prior successful context
   ↓
validate final outcome
```

The integration test [`tests/test_runtime_recovery.py`](tests/test_runtime_recovery.py) covers both **primary → backup → success** and **primary → first backup fails → second backup → success**, including trust degradation and recovery ordering.

### Durable multi-step resume

`DurableAgentWeave` persists completed steps before advancing the scheduler. A fresh process can load the same checkpoint and continue from the next unfinished step without replaying already-completed work.

```python
from agentweave import DurableAgentWeave, WorkflowStep

weave = DurableAgentWeave(db_path='agentweave.db')

steps = [
    WorkflowStep('collect', 'Collect evidence', {'research'}),
    WorkflowStep('analyze', 'Analyze the evidence', {'analysis'}),
    WorkflowStep('verify', 'Verify the conclusion', {'verification'}),
]

result = await weave.run_workflow(
    steps,
    workflow_id='case-42',
    max_failovers=2,
)

result = await weave.resume_workflow('case-42', max_failovers=2)
```

Checkpoint persistence is available through SQLite, PostgreSQL, and the replicated store path. See [`tests/test_durable_workflow.py`](tests/test_durable_workflow.py).

Completed steps are durable from the AgentWeave scheduler's perspective. A remote side effect that occurs immediately before process death but before checkpoint persistence remains **at-least-once** unless the remote implementation honors the stable `workflow_id:step_id` idempotency key.

## Security, identity, governance, and reliability

The proof suite covers malicious Agent Cards, prompt injection, data exfiltration, SSRF/link-local access, tool abuse, spoofing, Sybil/collusion, reputation poisoning, Byzantine disagreement, malformed results, and timeouts.

It also exercises:

- Docker isolation with read-only filesystem, tmpfs, network, secret, CPU, memory, and PID controls;
- JWT Verifiable Credentials, revocation, certificate/key rotation, and KMS/HSM integration boundaries;
- PostgreSQL concurrent writes, transaction/audit durability, reconnect recovery, and replica-aware behavior;
- governance for scopes, jurisdiction, residency, tools, locality, risk tiers, and human approval;
- chaos scenarios including disappearing or slow agents, network failure, malformed output, database failure, and process recovery.

A passing proof is evidence for the configured test runtime; it is not a formal security, HA, hardware-attestation, or compliance certification.

## Scalability

A physical GitHub Actions run evaluated synthetic populations of 10K, 100K, and 1M agents.

| Agents | Mode | Ranking time | Throughput | Peak RSS |
|---:|---|---:|---:|---:|
| 10,000 | Python | 0.0417 s | 239,526 agents/s | 82.0 MB |
| 10,000 | Native C++ path | 0.2787 s | 35,881 agents/s | 100.2 MB |
| 100,000 | Python | 1.1234 s | 89,018 agents/s | 255.0 MB |
| 100,000 | Native C++ path | 3.0936 s | 32,324 agents/s | 255.0 MB |
| 1,000,000 | Python | 11.9981 s | 83,346 agents/s | 299.1 MB |
| 1,000,000 | Native C++ path | 34.1091 s | 29,318 agents/s | 299.1 MB |

The native ranking path is slower than Python in this benchmark and is reported as such. Graph-ingestion measurements for the 100K and 1M runs use an explicitly bounded 50K graph sample rather than claiming a retained million-node graph.

## Evidence boundaries and data sources

| Category | Status | Current use |
|---|---|---|
| **Real systems / real execution** | ✅ | public A2A services, upstream SDK agents, official TCK, PostgreSQL, Docker/runtime controls, and executable workload handlers |
| **External public benchmark data** | ✅ | AgentBench, ToolBench, AgencyBench, AgentProcessBench, General-AgentBench, multiple external router holdouts, and BFCL questions used in the separately bounded routing-pressure studies |
| **Synthetic benchmark data** | ✅ | generated populations, controlled agent catalogs, proficiencies, cost/latency profiles, adversarial fixtures, and deterministic BFCL distractor augmentation |
| **Supervised benchmark routing data** | ✅ | AgencyBench development/other-fold scenario labels used only for separately reported supervised analyses |
| **Production / real-world agent traces** | ❌ not claimed | no private production-user corpus, billed cost traces, or human-rated production outcomes |

The repository does **not** present routing accuracy as native task completion, controlled synthetic execution as production performance, or BFCL routing-pressure numbers as official BFCL leaderboard scores.

Some proof also requires infrastructure outside the repository:

- AWS Bedrock / Microsoft Foundry / Google Cloud marketplace execution requires credentials and configured agents;
- Jetson / Raspberry Pi / NPU proof requires physical hardware;
- live cloud KMS/HSM/TPM/TEE evidence requires corresponding infrastructure;
- production adoption requires independent users, integrations, deployments, citations, and external reproductions.

## Release and compatibility

AgentWeave follows Semantic Versioning. [`CHANGELOG.md`](CHANGELOG.md), [`SECURITY.md`](SECURITY.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CITATION.cff`](CITATION.cff), [`docs/API_COMPATIBILITY.md`](docs/API_COMPATIBILITY.md), and [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md) define maintenance, citation, and compatibility policy.

The release workflow validates distributions and supports GitHub Release/PyPI trusted publishing when the corresponding release/tag and publishing configuration are present. Repository code and CI configuration alone are not presented as proof that a public package has already been published.

## Contributing

Contributions, interoperability reports, marketplace adapters, benchmark scenarios, security tests, documentation improvements, and real-world evaluation datasets are welcome.

- **Issues and feedback:** use GitHub Issues.
- **Pull requests:** see [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Compatibility work:** see [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md).
- **Security:** see [`SECURITY.md`](SECURITY.md).

## What's next

Current research and engineering priorities include:

- run broader benchmark-native task execution rather than routing-only evaluation;
- extend BFCL work using standard official-evaluation paths in addition to the bounded routing-pressure study;
- connect selection, execution, process verification, native judging, and reputation update in one benchmark-native loop;
- obtain independent external reproductions and integrations;
- expand real provider, hardware, and marketplace execution where credentials and infrastructure are available;
- continue improving learned/semantic routing while preserving frozen evidence and untouched test distributions.

## About

AgentWeave is an open-source project for research and engineering around interoperable, trustworthy, failure-aware multi-agent orchestration. A2A provides the communication layer; AgentWeave focuses on the decision, trust, team-formation, recovery, governance, and verification layers around it.

## License

Apache-2.0