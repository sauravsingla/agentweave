# AgentWeave

**Knowledge-, capability-, trust-, and policy-aware orchestration for heterogeneous AI agents.**

AgentWeave is an open-source framework for discovering, validating, selecting, and orchestrating AI agents across cloud, marketplaces, enterprise environments, and edge devices. It uses **A2A as the interoperability layer** and adds requirement intelligence, evidence-backed capability validation, contextual trust, knowledge graphs, global team optimization, governance, semantic verification, reputation learning, observability, sandboxing, and production proof tooling.

[![CI](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml)
[![Deep Proof](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml)
[![A2A SDK Interop](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml)
[![Protocol Depth](https://github.com/sauravsingla/agentweave/actions/workflows/protocol-depth.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/protocol-depth.yml)
[![External Proof](https://github.com/sauravsingla/agentweave/actions/workflows/external-proof.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/external-proof.yml)
[![AgentBench](https://github.com/sauravsingla/agentweave/actions/workflows/agentbench-external.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/agentbench-external.yml)

> **A2A answers:** how can agents communicate?
>
> **AgentWeave adds:** which agents should communicate for this requirement, can their expertise and identity be trusted, what should each do, where should they execute, and how should their outputs be validated and learned from?

## Why AgentWeave?

Modern agent ecosystems contain many heterogeneous agents with different skills, trust levels, costs, latencies, execution locations, security boundaries, and implementation stacks. Communication alone does not answer the routing and governance problem.

AgentWeave is designed to:

- **Discover agents** through A2A Agent Cards, registries, marketplaces, enterprise catalogs, and edge runtimes.
- **Validate claims** using benchmarks, evidence, identity, policy, freshness, and historical outcomes.
- **Match requirements to agents** using capability graphs, ontology relationships, semantic relevance, placement, cost, latency, and trust.
- **Form teams** with global optimization across coverage, trust, diversity, redundancy, cost, latency, and communication overhead.
- **Collaborate over A2A** with lifecycle, streaming, task management, cancellation, resume, subscription, and push-notification support.
- **Verify results** using contradiction checks, citation/source-quality checks, uncertainty calibration, NLI/verifier hooks, and consensus/conflict handling.
- **Learn from outcomes** through persistent reputation and dynamic re-testing.
- **Operate safely** with governance, sandboxing, observability, identity, credentials, and audit controls.

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
 Streaming / Long-running / Push Tasks
                    │
   Consensus + Conflict Resolution
                    │
     Result + Semantic Verification
                    │
      Reputation + Dynamic Retesting
```

## Key capabilities

### A2A interoperability and lifecycle

- Agent Card discovery.
- JSON-RPC and HTTP+JSON lifecycle support.
- Generated-stub gRPC lifecycle client.
- `SendMessage`, streaming, `GetTask`, `ListTasks`, `CancelTask`, task subscription, retry/resume, and push-notification configuration.
- Authenticated ASGI push-notification receiver.
- Official A2A TCK integration.
- Cross-SDK interoperability proof using Python, Go, JavaScript, and Java implementations.
- Independently hosted real-internet A2A proof.

### Trust, identity, security, and governance

- Contextual trust vectors rather than one opaque trust score.
- `did:web` plus pluggable DID resolution.
- JWT Verifiable Credential verification and revocation.
- Certificate/key rotation and KMS/HSM integration boundary.
- Workload-attestation verification boundary.
- Malicious Agent Card, prompt-injection, data-exfiltration, SSRF/link-local, tool-abuse, identity-spoofing, Sybil/collusion, reputation-poisoning, Byzantine, timeout, and malformed-result tests.
- Docker sandboxing with read-only filesystem, tmpfs, network, secret, CPU, memory, and PID controls.
- Bubblewrap support where the host permits user namespaces.
- Governance for principal/scopes, jurisdiction, data residency, tools, locality, risk tiers, and human approval.

### Knowledge, matching, and optimization

- Capability and knowledge graphs.
- RDF/SKOS ontology import.
- Aliases, inheritance, semantic similarity, contradiction relationships, and temporal freshness.
- Requirement-aware matching and placement.
- Global team optimization across coverage, trust, diversity, latency, cost, redundancy, and communication overhead.
- Python implementation plus C++/pybind native ranking/team-selection paths.

### Verification, persistence, and observability

- Citation and source-quality checks.
- Contradiction/NLI hooks.
- Verifier-agent hooks.
- Brier score, ECE, and classification metrics for calibration evaluation.
- SQLite for local use and PostgreSQL for production-oriented persistence.
- Concurrent writes, transaction/audit proof, reconnect recovery, and replica-aware proof tooling.
- Structured logs, metrics, OpenTelemetry-compatible spans, selection explanations, and audit history.

## Verified test results

The core proof results below were established on commit `cadf2d4c517bfae07536e6c37332beac7f06ef6d` on **2026-08-15**. The external AgentBench evaluation was added later and is reported separately with its own commit and data boundary.

### Workflow status

| Proof | Result | What was exercised |
|---|---:|---|
| CI | ✅ PASS | Python tests, package install, C++ build/native smoke |
| AgentWeave Deep Proof | ✅ PASS | A2A TCK, security, sandbox, identity, PostgreSQL, scale, research, verification, governance, chaos |
| Protocol Depth Proof | ✅ PASS | lifecycle/gRPC dispatch/push contract tests |
| A2A SDK Interoperability Proof | ✅ PASS | Python, Go, JavaScript, Java A2A agents |
| External Environment Proof | ✅ PASS | independently hosted public A2A services |
| AgentBench External Data Evaluation | ✅ PASS | external published task text, blind routing, selective routing, evidence artifacts |

### Cross-SDK A2A interoperability

AgentWeave launched independent upstream A2A SDK agents, waited for each Agent Card, discovered each agent, and completed a live invocation.

| SDK implementation | Agent Card discovery | Invocation | Result |
|---|---:|---:|---:|
| Python | ✅ | ✅ | PASS |
| Go | ✅ | ✅ | PASS |
| JavaScript | ✅ | ✅ | PASS |
| Java | ✅ | ✅ | PASS |

### Real independently hosted A2A proof

The external proof used public internet services not hosted by AgentWeave CI.

| Service | Discovery | Real invocation | Notes |
|---|---:|---:|---|
| Deep Research Archives | ✅ | ✅ | Structured JSON-RPC `SendMessage` request |
| Delx Agent Operations Protocol | ✅ | ✅ | Public registration bootstrap, credential capture, authenticated `message/send` |

This is different from the controlled SDK test above: these services are independently hosted and were contacted over the public internet.

### Official A2A conformance

The Deep Proof workflow launches AgentWeave as an A2A system under test and executes the official A2A TCK with:

```bash
uv run ./run_tck.py --sut-host http://127.0.0.1:9998 --transport jsonrpc --level must
```

Result: **✅ PASS — JSON-RPC MUST-level TCK**.

### 10K / 100K / 1M scalability benchmark

Benchmark environment:

- Python 3.11.15
- Ubuntu 24.04 GitHub-hosted Azure runner
- GCC 13.3.0
- native extension available
- synthetic agents generated reproducibly from a fixed-seed capability/trust/execution distribution
- capability pool: `analysis`, `research`, `coding`, `summarization`, `planning`, `vision`, `retrieval`, `verification`

The ranking benchmark physically evaluated the requested populations; it did **not** relabel a smaller run as a larger one.

| Agents | Mode | Ranking time | Throughput | Peak RSS |
|---:|---|---:|---:|---:|
| 10,000 | Python | 0.0417 s | 239,526 agents/s | 82.0 MB |
| 10,000 | Native C++ path | 0.2787 s | 35,881 agents/s | 100.2 MB |
| 100,000 | Python | 1.1234 s | 89,018 agents/s | 255.0 MB |
| 100,000 | Native C++ path | 3.0936 s | 32,324 agents/s | 255.0 MB |
| 1,000,000 | Python | 11.9981 s | 83,346 agents/s | 299.1 MB |
| 1,000,000 | Native C++ path | 34.1091 s | 29,318 agents/s | 299.1 MB |

**Important:** in this current benchmark, the native ranking path is slower than the Python path. AgentWeave publishes that result rather than presenting the native implementation as an automatic speedup. The native team-selection microbenchmark reached approximately **4,859 ops/s at 10K**, **1,284 ops/s at 100K**, and **1,033 ops/s at 1M** in the same run.

Graph-ingestion measurements used explicit bounded samples: 10K agents for the 10K run and 50K agents for the 100K/1M runs. The 50K sample produced **50,008 nodes / 124,845 edges**, with about **75.6K graph updates/s** in the 100K run and **67.2K updates/s** in the 1M run. This is intentionally reported as a sample, not as a million-node retained graph.

### Research evaluation

The current publication package uses a reproducible **synthetic benchmark dataset**, not a claim of real-world human task accuracy. Baselines include random, single-best, trust-only, capability-greedy, embedding-only, plus no-trust/no-placement ablations.

Selected aggregate results from the latest green run:

| Method | Coverage | Trust | Latency | Cost | Quality proxy |
|---|---:|---:|---:|---:|---:|
| AgentWeave | 0.7604 | 0.7524 | 77.8 ms | 0.2222 | 0.6201 |
| Single-best | 0.7604 | 0.6822 | 298.3 ms | 0.5181 | 0.6324 |
| Random | 0.2354 | 0.5384 | 554.8 ms | 0.5037 | 0.1674 |
| Trust-only | 0.4833 | 0.8027 | 448.6 ms | 0.6440 | 0.4101 |
| Capability-greedy | 0.7604 | 0.6030 | 289.2 ms | 0.4974 | 0.6324 |
| Embedding-only | 0.7604 | 0.6822 | 319.5 ms | 0.5159 | 0.6324 |

The `quality_proxy` is a routing/evaluation metric, **not** a claim of factual correctness or human preference. In the current synthetic evaluation, AgentWeave strongly improves latency/cost/trust versus several baselines while matching single-best coverage, but the quality proxy is slightly below the single-best baseline. This result is intentionally reported as measured.

Generated research artifacts:

- `research-evaluation.json`
- `research-evaluation.csv`
- `research-evaluation.md`
- `research-coverage.svg`
- `research/METHODOLOGY.md`
- `research/benchmark_cases.json`

### External AgentBench routing evaluation

AgentWeave is also evaluated against **external published benchmark data** from the official `THUDM/AgentBench` repository, pinned to commit `d1e4a10db08c87075c78972e48ecc182be03e2d5`. The latest evaluation workflow ran on AgentWeave commit `5db8b075332a75d73905c125e0c614e74d61b513`.

The evaluation uses **490 published AgentBench tasks**:

| AgentBench environment | Tasks |
|---|---:|
| DBBench | 200 |
| KnowledgeGraph | 150 |
| OS Interaction | 140 |
| **Total** | **490** |

Three related tests are reported because they answer different questions:

| Evaluation | What the router sees | Result | Correct interpretation |
|---|---|---:|---|
| **Label-informed matching** | Task text plus requirement/domain derived from the published environment label | **100.0% specialist selection** | Tests matching/ranking once the required expertise is already known; **not a blind result** |
| **Blind text-only routing** | Raw task text only; AgentBench environment label withheld until scoring | **34.1% specialist selection over all 490 tasks** | Tests AgentWeave's current requirement inference plus routing without label leakage |
| **Confidence-aware selective routing** | Raw task text only; router may abstain when specialist evidence is insufficient | **96.0% accuracy on committed routes at 35.5% coverage** | Measures precision when AgentWeave has enough evidence to commit; abstentions are not counted as correct routes |

For the confidence-aware blind run, AgentWeave committed on **174 / 490 tasks**, correctly selected the specialist on **167 tasks**, and abstained on **316 tasks**. This is **34.1% correct specialist selection across the full dataset**, not 96% across all tasks.

Per-domain selective-routing results:

| Domain | Tasks | Committed | Coverage | Accuracy when committed |
|---|---:|---:|---:|---:|
| Database | 200 | 63 | 31.5% | **100.0%** |
| Knowledge graph | 150 | 0 | 0.0% | N/A — no committed route |
| Operating system | 140 | 111 | 79.3% | **93.7%** |

The blind text-only comparison against simple baselines was:

| Method | Blind specialist-selection rate |
|---|---:|
| **AgentWeave** | **34.1%** |
| Random | 19.2% |
| Capability-only | 0.2% |
| Single-best | 0.0% |
| Trust-only | 0.0% |

**Dataset and metric boundary:**

- **External published data:** AgentBench task text and held-out environment/domain labels from DBBench, KnowledgeGraph, and OS Interaction.
- **Synthetic data:** the candidate-agent catalog used for this routing experiment, including specialist/generalist identities, proficiency, validation flags, trust values, latency, and cost.
- **Real measurement:** routing computation time is measured during the GitHub Actions run.
- **Held-out label use:** in the blind and selective tests, the AgentBench environment label is used only after routing as ground truth for scoring.
- **Not claimed:** these numbers are **not** the original AgentBench end-to-end environment success rate, LLM answer quality, production-user accuracy, real provider latency, or billed model cost.
- **Known limitation:** KnowledgeGraph had 0% selective coverage because the current deterministic text analyzer often lacks enough observable evidence to infer the hidden backend/domain from the raw question alone. This motivates a future semantic/LLM requirement-inference layer rather than benchmark-specific label leakage.

Evidence is produced by `.github/workflows/agentbench-external.yml` and uploaded as JSON/Markdown artifacts for the label-informed, blind, and selective evaluations.

### Security, storage, identity, governance, and reliability

The latest Deep Proof run also completed successfully for:

- red-team + Docker/Bubblewrap sandbox proof;
- identity, VC, revocation, KMS boundary, and attestation proof;
- PostgreSQL concurrency, recovery, replica-aware behavior, and audit durability proof;
- result-verification quality/calibration proof;
- governance policy scenarios;
- disappearing/slow/malformed/network/database/process recovery chaos scenarios.

A passing proof means the configured control behaved as expected in that test runtime. It is **not** a formal security certification, HA certification, or hardware-attestation certification.

## What data is used?

AgentWeave distinguishes four different things that are easy to confuse: **real systems / real execution**, **external public benchmark data**, **synthetic benchmark data**, and **production/real-world task traces**.

| Category | Current status | What AgentWeave uses today |
|---|---|---|
| **Real systems / real execution** | ✅ Used and tested | Independently hosted public A2A services, live upstream SDK agents, official A2A TCK, a real PostgreSQL service, and real Docker/runtime isolation behavior |
| **External public benchmark data** | ✅ Used | 490 published AgentBench task records from DBBench, KnowledgeGraph, and OS Interaction, pinned to a specific upstream commit |
| **Synthetic benchmark data** | ✅ Used | Generated agent populations, capabilities, trust values, latency/cost distributions, routing scenarios, adversarial fixtures, and the candidate-agent catalog used in the AgentBench routing experiment |
| **Production / real-world agent traces** | ❌ Not yet included | No private production-user task corpus, production agent histories, billed provider cost traces, or human-rated production outcomes are claimed |

### What “real” means in the current results

“Real” can refer to different evidence types, so AgentWeave reports them separately rather than treating all non-synthetic evidence as equivalent.

The real execution evidence includes:

- **Deep Research Archives:** AgentWeave discovered an independently hosted Agent Card over the public internet and completed a live structured A2A invocation.
- **Delx Agent Operations Protocol:** AgentWeave used the live registration endpoint, received a runtime credential, and completed an authenticated A2A `message/send` call.
- **Python / Go / JavaScript / Java A2A SDK agents:** actual upstream SDK implementations were launched in CI, discovered, and invoked.
- **Official A2A TCK:** the official JSON-RPC MUST-level conformance suite was executed against AgentWeave as the system under test.
- **PostgreSQL:** concurrency, transactional writes, recovery, replication/audit behavior, and reconnect logic were exercised against a real PostgreSQL service in CI.
- **Docker/runtime security:** actual container/runtime isolation controls were executed rather than simulated.
- **10K / 100K / 1M scale execution:** the benchmark physically processed those synthetic agent records; the execution is real even though the records themselves are synthetic.

### What external benchmark data is used

AgentWeave currently uses a pinned subset of the public **AgentBench** repository for an external routing evaluation:

- DBBench task descriptions — 200 tasks;
- KnowledgeGraph questions — 150 tasks;
- OS Interaction task descriptions — 140 tasks.

The task text is external published benchmark data. In blind tests, the associated environment/domain label is withheld from the router and used only afterward for scoring. This should be interpreted as an **external benchmark routing evaluation**, not as production-user data or the original end-to-end AgentBench success metric.

### What is synthetic today

The scalability and internal research evaluations still use generated data. Synthetic fields include:

- agent capability assignments from the pool `analysis`, `research`, `coding`, `summarization`, `planning`, `vision`, `retrieval`, and `verification`;
- capability-strength/evidence values;
- contextual trust-vector values;
- cloud/edge execution placement;
- latency and cost values;
- research routing scenarios and expected capability requirements;
- the fixed candidate-agent catalog used to score AgentBench specialist selection;
- malicious Agent Cards and prompt-injection fixtures;
- Sybil/collusion clusters;
- poisoned reputation histories;
- Byzantine/disagreement responses;
- timeout, malformed-result, and other adversarial fixtures.

The synthetic populations are generated reproducibly with fixed seeds where applicable so the benchmark can be repeated.

### Production / real-world task-data status

AgentWeave **does not claim production-user or human-rated real-world task evaluation yet**. The AgentBench results are an important external-data step, but they should not be interpreted as accuracy on private production tasks, real agent histories, human-rated task outcomes, production provider latency, or billed cost.

A future research milestone is to add end-to-end task execution on published agent benchmarks and/or independently collected agent-task traces with known outcomes, then report task success, answer quality, cost, latency, failure rate, routing benefit, team-selection benefit, and calibration against appropriate baselines.

## Getting started

### Install

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
    bus.register_handler(
        'research-1',
        lambda task: {'result': 'evidence-backed finding', 'decision': 'accept'},
    )

    result = await weave.solve(
        'Research the topic',
        rounds=1,
        semantic_verify=True,
    )
    print(result)

asyncio.run(main())
```

## Run the proof suites locally

```bash
python scripts/security_proof.py
python scripts/identity_proof.py
python scripts/chaos_proof.py
python scripts/governance_proof.py
python scripts/verification_proof.py
python scripts/research_evaluation.py
```

Scale suite:

```bash
PYTHONPATH=cpp/build python scripts/scale_suite.py --sizes 10000,100000,1000000
```

PostgreSQL proof:

```bash
export AGENTWEAVE_POSTGRES_DSN='postgresql://agentweave:agentweave@127.0.0.1:5432/agentweave'
python scripts/storage_proof.py
```

## CLI / SDK

```bash
agentweave version
agentweave doctor
agentweave graph-stats
agentweave plugins
agentweave --config agentweave.yaml config-check
agentweave solve --semantic-verify "Research and verify this topic"
```

`AgentWeaveSDK.API_VERSION` defines the high-level SDK contract. See `docs/API_COMPATIBILITY.md` for compatibility/deprecation rules and `examples/plugin_example.py` for a plugin skeleton.

## External environment boundaries

Repository code cannot manufacture external evidence. These proofs require real infrastructure:

- AWS Bedrock / Microsoft Foundry / Google Cloud marketplace tests require valid credentials and procured/configured agents.
- Physical Jetson / Raspberry Pi / NPU measurements require a registered self-hosted `agentweave-edge` runner and actual hardware.
- Live KMS/HSM/TPM/TEE evidence requires the corresponding external infrastructure.

The workflows fail closed or skip gated jobs when these resources are absent rather than reporting synthetic success.

## Deployment

`deploy/docker-compose.yml` provides PostgreSQL and Ollama services for local integration/development environments.

## Release engineering

AgentWeave follows Semantic Versioning. `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CITATION.cff`, and `docs/API_COMPATIBILITY.md` define release and maintenance policy. A `vX.Y.Z` tag triggers the release workflow, distribution validation, GitHub Release creation, and PyPI trusted publishing when configured.

## Contributing

Contributions, interoperability reports, new marketplace adapters, benchmark scenarios, security tests, and real-world evaluation datasets are welcome. See `CONTRIBUTING.md`.

## License

Apache-2.0