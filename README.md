# AgentWeave

AgentWeave is a domain-agnostic framework for discovering, validating, selecting, and orchestrating heterogeneous AI agents across cloud, marketplaces, enterprise, and edge environments. A2A is the interoperability layer; AgentWeave adds requirement-aware discovery, evidence-backed capability validation, contextual trust, policy, team optimization, collaboration, semantic result verification, reputation, observability, and resource-aware placement.

## Architecture

```text
Cloud / Marketplace / Enterprise / Edge Agents
                    |
              Agent Registry
                    |
       Security + Identity + Benchmarks
                    |
       Capability + Knowledge Ontology
                    |
             Contextual Trust
                    |
          Matching + Placement
                    |
          Global Team Optimizer
                    |
                   A2A
                    |
      Multi-round / Streaming Tasks
                    |
      Consensus + Conflict Resolution
                    |
      Result + Semantic Verification
                    |
       Reputation + Dynamic Retesting
```

## Implemented

AgentWeave includes A2A Agent Card discovery and JSON-RPC/HTTP+JSON clients, multi-round collaboration, consensus/conflict handling, semantic result verification, benchmark-based capability validation, DID/VC and signature hooks, security validation, Docker/Bubblewrap sandboxing, ontology-aware capability/knowledge graphs, global team optimization, PostgreSQL/SQLite reputation storage, observability, governance, edge runtimes, marketplace connectors, and optional C++/pybind11 acceleration.

The repository also contains live cross-SDK A2A interoperability CI. Python, Go, JavaScript and Java upstream A2A SDK agents are launched independently and AgentWeave discovers and invokes each of them.

## Deep proof suite

Version 0.5 adds reproducible proof infrastructure for the five remaining maturity areas:

1. **Full A2A lifecycle + TCK conformance** — `LongRunningA2AClient` supports SendMessage, SendStreamingMessage, GetTask, ListTasks, CancelTask and resumable polling for JSON-RPC and HTTP+JSON. `agentweave.a2a_server` is an AgentWeave A2A System Under Test built with the official Python A2A SDK. CI launches it and runs the official Linux Foundation `a2aproject/a2a-tck` MUST-level JSON-RPC suite.
2. **Adversarial/security + sandbox validation** — deterministic prompt-injection/Sybil fixtures plus active Docker isolation tests for read-only root filesystem, writable tmpfs, disabled network, secret isolation, PID, CPU and memory limits.
3. **10K/100K/1M scalability + C++ benchmarks** — `ScaleSuite` physically evaluates the requested population using bounded-memory batches and compares Python against the native C++ matcher when the pybind11 module is available. The 10K proof runs in normal CI; the 10K/100K/1M physical run is available from the Deep Proof workflow.
4. **Research baselines + ablations** — reproducible comparisons against random routing, single-best, trust-only and capability-greedy baselines, plus no-trust and no-placement ablations. Reports include per-case metrics, aggregate coverage/score/trust/latency/cost/team-size and bootstrap confidence intervals.
5. **Real deployment proof** — PostgreSQL is exercised in CI using a real PostgreSQL service with agent and outcome round-trips. AWS Bedrock, Microsoft Foundry and Google Cloud Marketplace proof jobs use real credentials/card URLs when configured. Real edge proof runs on a self-hosted `agentweave-edge` runner against an installed Ollama or llama.cpp runtime and records hardware/runtime telemetry.

## Install

```bash
python -m pip install -e '.[dev]'
pytest -q
```

For the A2A conformance SUT:

```bash
python -m pip install -e '.[tck]'
agentweave-a2a-sut
```

Optional production integrations:

```bash
python -m pip install -e '.[security,postgres,aws,observability,edge,yaml,native]'
```

## A2A interoperability and lifecycle

The **A2A SDK Interoperability Proof** workflow launches independent upstream Python, Go, JavaScript and Java A2A implementations and produces a compatibility-matrix artifact. The **AgentWeave Deep Proof** workflow additionally starts the AgentWeave A2A SUT, exercises normal and streaming lifecycle operations, then runs the official TCK against it.

The lifecycle client can also be used directly:

```python
from agentweave import AgentCardDiscovery, LongRunningA2AClient

agent = await AgentCardDiscovery().fetch('https://agent.example/.well-known/agent-card.json')
client = LongRunningA2AClient()
state = await client.send(agent, 'research this topic')
async for event in client.stream(agent, 'stream progress'):
    print(event)
```

## Security proof

```bash
python scripts/security_proof.py
```

This actively runs sandbox attack cases when Docker is available. A passing security proof means the tested controls behaved as configured on that runtime; it is not a formal security certification.

## Research evaluation

```bash
python scripts/research_evaluation.py
```

The generated `research-evaluation.json` contains baseline and ablation rows, aggregate metrics and a bootstrap 95% confidence interval for AgentWeave's coverage delta versus the single-best baseline.

## Scalability

```bash
PYTHONPATH=cpp/build python scripts/scale_suite.py --sizes 10000,100000,1000000
```

The reported `physical_agents_evaluated` field equals the requested population. Batching bounds memory without relabeling smaller runs as larger ones.

## PostgreSQL and live deployments

```python
from agentweave import PostgresReputationStore
store = PostgresReputationStore('postgresql://user:pass@host/db')
```

`PostgresDeploymentProof` verifies registry persistence plus outcome/audit writes. `MarketplaceDeploymentProof` executes AWS Bedrock, Microsoft Foundry and Google Cloud A2A marketplace connectors when their environment configuration is present. `EdgeDeploymentProof` invokes a real Ollama or llama.cpp model and records latency, memory, CPU, GPU and thermal telemetry where available.

## Production boundary

The repository distinguishes **implemented test harnesses** from **executed external proof**. PostgreSQL, Docker, A2A SDK interoperability and CI-based conformance can be exercised on GitHub-hosted runners. Marketplace proof requires valid cloud credentials/procured Agent Card URLs, and real edge proof requires a registered self-hosted hardware runner with the selected model/runtime installed. The workflow fails rather than claiming a live proof when a required live target is not configured.

## License

Apache-2.0
