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

## What is implemented

- Live A2A endpoint interoperability harness and official `a2aproject/a2a-tck` workflow integration.
- A2A Agent Card discovery and JSON-RPC / HTTP+JSON clients, plus long-running streaming, retry, cancel and resume lifecycle helpers.
- Ecosystem connectors for Amazon Bedrock agents, Microsoft Foundry Agents, Google Cloud Marketplace A2A Agent Cards, curated A2A catalogs, and generic HTTP catalogs.
- Benchmark-based capability validation and dynamic re-testing.
- Composite result validation plus semantic consistency, contradiction, uncertainty, citation/evidence and verifier-agent hooks.
- DID resolution (`did:web` plus universal-resolver adapter), JWT Verifiable Credential verification, revocation, certificate rotation, external KMS/HSM hooks, and workload/hardware attestation hooks.
- Container sandboxing with Docker (`cap-drop=ALL`, no-new-privileges, read-only root, network isolation, memory/CPU/PID limits, tmpfs and secret allow-listing) plus Bubblewrap support.
- Ontology-aware knowledge/capability graph with aliases, inheritance, semantic similarity and freshness decay.
- Global team optimization over coverage, trust, diversity, redundancy, latency, cost and communication overhead.
- SQLite development storage and transactional PostgreSQL registry/reputation storage with audit history and optional write-through replicas.
- Synthetic 10K/100K/1M-agent scalability benchmark harness, C++/Python routing comparison hooks and research-baseline evaluation.
- Adversarial tests for lying Agent Cards, prompt-injection strings, Sybil groups, reputation poisoning, timeouts and Byzantine disagreement.
- Edge runtime adapters for Ollama and llama.cpp plus hardware telemetry/test harness for CPU, memory, NVIDIA GPU, thermal data and reconnect/offline simulation.
- Structured logging, metrics, OpenTelemetry-compatible tracing and audit trails.
- Governance policy engine for jurisdiction, data residency, tool authorization, locality, risk tiers and human approval.
- CLI, JSON/YAML configuration, plugin entry points and stable SDK facade.
- Optional pybind11 C++ native ranking acceleration with CI import/execution tests.

## Install

```bash
python -m pip install -e '.[dev]'
pytest -q
```

Optional production integrations:

```bash
python -m pip install -e '.[security,postgres,aws,observability,edge,yaml,native]'
```

## Minimal example

```python
import asyncio
from agentweave import AgentWeave, AgentProfile, Capability, InMemoryA2AAdapter

async def main():
    bus = InMemoryA2AAdapter()
    weave = AgentWeave(a2a=bus, db_path=':memory:')
    agent = AgentProfile('research-1', 'Research Agent', [Capability('research', .9, True)])
    weave.register(agent)
    bus.register_handler('research-1', lambda task: {'result': 'evidence-backed finding', 'decision': 'accept'})
    result = await weave.solve('Research the topic', rounds=1, semantic_verify=True)
    print(result)

asyncio.run(main())
```

## Live A2A interoperability

The repository contains a manual GitHub Actions workflow, **Live A2A Interoperability**, that accepts multiple independent A2A Agent Card URLs. It performs discovery and invocation against each target. An optional `sut_host` input also clones and runs the official Linux Foundation A2A TCK MUST-level conformance suite.

Locally:

```bash
export AGENTWEAVE_A2A_TARGETS='[
  {"name":"python-agent","agent_card_url":"https://host-a/.well-known/agent-card.json","implementation":"a2a-python"},
  {"name":"java-agent","agent_card_url":"https://host-b/.well-known/agent-card.json","implementation":"a2a-java"}
]'
python scripts/live_interop.py
```

The official A2A sample project contains implementations in Python, Go, Java, JavaScript and .NET; these are suitable targets for a multi-language interoperability lab. AgentWeave intentionally does not hard-code public demo endpoints because those endpoints are not guaranteed to remain available.

## Marketplace connectors

`AWSBedrockAgentConnector` lists agents in an authenticated AWS account. `MicrosoftFoundryAgentConnector` uses the Foundry Agents REST API. `GoogleCloudMarketplaceA2AConnector` loads procured Google Cloud Marketplace A2A Agent Cards; Google Cloud's A2A marketplace flow exposes the Agent Card associated with a procured agent rather than a universal unauthenticated agent-catalog API.

## Sandboxing

Use `DockerSandbox` for untrusted code execution. Images should be digest pinned and optionally allow-listed via `SandboxPolicy`. Sandbox execution is an OS-level control, but production deployments should still use hardened container runtimes/VMs, image signing, network policy and host security appropriate to their threat model.

## PostgreSQL

```python
from agentweave import AgentWeave, PostgresReputationStore
store = PostgresReputationStore('postgresql://user:pass@host/db')
weave = AgentWeave(store=store)
```

The PostgreSQL backend uses transactions, versioned agent records, indexed outcome history and an append-only audit table. `ReplicatedStore` supports write-through replicas.

## Scalability benchmark

```bash
python scripts/scale_benchmark.py --sizes 10000,100000,1000000
```

For constrained CI or development machines, use `--cap` to execute a smaller physical population while preserving requested-size labels. Do not publish capped results as million-agent measurements.

## CLI

```bash
agentweave agents
agentweave --config agentweave.json solve "Research and verify this topic"
```

## Production boundary

AgentWeave now contains implementations for each major architectural layer, but external-service and hardware capabilities require the corresponding credentials, services, runtimes or devices. A connector existing in code is not evidence that a specific marketplace account, remote A2A server, TPM/TEE, Jetson/Raspberry Pi, PostgreSQL cluster or container runtime has been exercised. Keep live interoperability, adversarial, scale and hardware results separate from unit-test claims.

## License

Apache-2.0
