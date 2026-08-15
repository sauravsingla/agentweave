# AgentWeave

AgentWeave is a domain-agnostic framework for discovering, validating, selecting, and orchestrating heterogeneous AI agents across cloud, marketplaces, enterprise, and edge environments. A2A is the interoperability layer; AgentWeave adds requirement-aware discovery, evidence-backed capability validation, contextual trust, policy, team optimization, collaboration, semantic result verification, reputation, observability, resource-aware placement and production-proof tooling.

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
 Streaming / Long-running / Push Tasks
                    |
      Consensus + Conflict Resolution
                    |
      Result + Semantic Verification
                    |
       Reputation + Dynamic Retesting
```

## v0.6 maturity expansion

Version 0.6 closes the remaining **implementation** gaps identified after the initial deep-proof work:

- A2A lifecycle over JSON-RPC/HTTP+JSON plus a generated-stub **gRPC lifecycle client** covering SendMessage, SendStreamingMessage, SubscribeToTask, GetTask, ListTasks, CancelTask and task push-notification configuration operations.
- A2A **push-notification** configuration client and authenticated ASGI webhook receiver.
- Official Linux Foundation A2A TCK MUST-level JSON-RPC proof against an AgentWeave SUT, plus cross-SDK Python/Go/JavaScript/Java live interoperability CI.
- Expanded red-team coverage for malicious Agent Cards, prompt/data-exfiltration instructions, SSRF/link-local access, tool abuse, identity spoofing, Sybil/collusion, reputation-poisoning fixtures, Byzantine disagreement, timeouts and malformed results.
- Active Docker sandbox proof for read-only filesystem, tmpfs, network isolation, secret isolation and cgroup CPU/memory/PID limits; Bubblewrap proof support is exercised where the runner permits user namespaces.
- DID/VC, revocation, certificate-rotation, KMS/HSM boundary and workload-attestation proof code, with live DID/real hardware attestation remaining environment-dependent.
- PostgreSQL concurrency, transactional outcome/audit writes, reconnect recovery, isolated write-through replica proof and durability counts.
- Physical 10K/100K/1M matcher benchmark workflow with Python/native C++ comparison, memory, team-selection throughput and explicit graph-ingestion sample metrics.
- Native C++ team-selection bridge in addition to native ranking.
- Research baselines for random, single-best, trust-only, capability-greedy, embedding-only and native-greedy routing; no-trust/no-placement ablations, redundancy/diversity/quality-proxy metrics and bootstrap confidence intervals.
- Ontology import, RDF/SKOS ingestion, aliases, inheritance, contradiction relationships, semantic retrieval and temporal freshness.
- Result verification with citation/source-quality hooks, NLI contradiction hooks, verifier-agent support and calibration metrics (Brier score/ECE/classification metrics).
- End-to-end span capture and OpenTelemetry-compatible tracing across requirement analysis, policy, matching, team selection, A2A collaboration, validation and reputation updates; selection explanations and audit history are returned with solve results.
- Governance scenario proofs for jurisdiction, residency, tools, locality, risk tiers and human approval.
- Chaos/reliability tests for disappearing agents, slow agents, network partitions, malformed responses, database failures and process-reopen recovery.
- Versioned SDK facade, richer CLI, plugin example, deployment template, API compatibility policy, security policy, contribution guide, changelog and tag-driven release/PyPI workflow.

## Install

```bash
python -m pip install -e '.[dev]'
pytest -q
```

Optional integrations:

```bash
python -m pip install -e '.[security,api,tck,grpc,native,postgres,aws,observability,edge,yaml,ontology]'
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

## A2A protocol depth

`LongRunningA2AClient` implements JSON-RPC and HTTP+JSON lifecycle operations including retries, streaming, task subscription, polling/resume, task listing and cancellation. `GrpcA2ALifecycleClient` works with the generated A2A protobuf module and gRPC stub so AgentWeave is not coupled to one SDK package layout. `PushNotificationConfigClient` manages task webhook configuration, while `PushNotificationReceiver` provides an HMAC-capable ASGI receiver.

The **AgentWeave Deep Proof** workflow launches the AgentWeave A2A SUT and runs the official A2A TCK MUST-level JSON-RPC suite. The **A2A SDK Interoperability Proof** independently launches upstream Python, Go, JavaScript and Java A2A agents and proves Agent Card discovery plus live invocation. The **Protocol Depth Proof** contract-tests the complete gRPC lifecycle dispatch surface and push receiver without pretending that a contract test is an external gRPC server proof.

## Security and reliability proof

```bash
python scripts/security_proof.py
python scripts/identity_proof.py
python scripts/chaos_proof.py
python scripts/governance_proof.py
python scripts/verification_proof.py
```

A passing proof means the tested control behaved as configured on that runtime; it is not a formal security certification. Production deployments should still use hardened container/VM runtimes, workload identity, secret management, signed images and network policy appropriate to their threat model.

## PostgreSQL proof

```bash
export AGENTWEAVE_POSTGRES_DSN='postgresql://agentweave:agentweave@127.0.0.1:5432/agentweave'
python scripts/storage_proof.py
```

The proof performs concurrent writes, outcome/audit transactions, process reconnect/recovery and write-through replication into an isolated replica namespace. This validates AgentWeave replication/recovery behavior against a real PostgreSQL service; it is not a claim of multi-node PostgreSQL HA certification.

## Research publication package

```bash
python scripts/research_evaluation.py
```

This generates:

- `research-evaluation.json` — complete machine-readable experiment and raw rows.
- `research-evaluation.csv` — per-case/per-method data.
- `research-evaluation.md` — paper-friendly aggregate table and confidence intervals.
- `research-coverage.svg` — dependency-free benchmark figure.
- `research/METHODOLOGY.md` and `research/benchmark_cases.json` — versioned experimental protocol and dataset.

The declared `quality_proxy` is a routing metric, not a claim of human-equivalent factual correctness.

## Physical scale suite

```bash
PYTHONPATH=cpp/build python scripts/scale_suite.py --sizes 10000,100000,1000000
```

The workflow physically processes the requested population in bounded-memory batches and never relabels a smaller population as a larger measurement. Output includes ranking wall time, agents/second, peak RSS, team-selection throughput, graph-ingestion sample throughput and Python/native C++ speedup where the native extension is available. The graph-ingestion metric reports its explicit sample size rather than presenting a bounded sample as a million-node retained graph.

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

## External proof boundary

Some claims cannot be truthfully manufactured by repository code alone. AgentWeave therefore fails closed and keeps **implemented proof harnesses** separate from **executed external evidence**:

- Independently hosted third-party A2A agents require two or more actual remote Agent Card URLs via `AGENTWEAVE_EXTERNAL_A2A_TARGETS` and the `External Environment Proof` workflow.
- Real AWS Bedrock, Microsoft Foundry and Google Cloud Marketplace proof requires valid account credentials/procured Agent Card URLs.
- Physical Jetson/Raspberry Pi/NPU evidence requires a registered self-hosted `agentweave-edge` runner with the selected runtime/model installed.
- Live DID/KMS/HSM/TPM/TEE evidence requires the corresponding external resolver or attestation infrastructure.

The code and workflows for those proofs are present, but the README does not label them "proven" until their real external target is configured and successfully exercised.

## Deployment template

`deploy/docker-compose.yml` provides local PostgreSQL and Ollama services for integration/development environments.

## Release engineering

AgentWeave follows Semantic Versioning. `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md` and `docs/API_COMPATIBILITY.md` define release and maintenance policy. Pushing a `vX.Y.Z` tag triggers the Release workflow, which tests, builds, validates, creates a GitHub release and uses PyPI trusted publishing when configured.

## License

Apache-2.0
