# Changelog

All notable changes to AgentWeave are documented here. The project follows Semantic Versioning.

## [Unreleased]

### Added
- Repository-relative Markdown link checker covering README, CONTRIBUTING, and docs, with a focused unit test for broken local targets.
- Runnable in-process multi-MCP example demonstrating duplicate `search` names, model-visible aliases, and verified dispatch to both providers.
- A provider-neutral local runtime example with three tools, routing visibility, and callable execution, requiring no model service or optional integration packages.

### Fixed
- Close file-backed reputation database connections after each operation, including failures, so Windows can release database files without waiting for garbage collection. In-memory stores retain their shared connection.

### Planned
- Additional independently hosted A2A endpoints and physical edge-hardware evidence as environments become available.
- Additional external provider/model reproductions using the credentialed Issue #38 live protocol.

## [0.7.0] - 2026-09-23

### Added
- Canonical `AgentWeaveRuntime` pipeline: catalog → deterministic scope → routing → model → schema validation → authorization → execution → bounded recovery.
- Provider-neutral `ToolSpec`, `ToolCall`, `ToolResult`, `ModelResponse`, `RunContext`, `RuntimeResult`, and runtime telemetry contracts.
- Canonical tool identity separate from model-visible function aliases, preventing silent cross-provider name collapse.
- JSON Schema validation before authorization/execution and argument-aware authorization context/hooks.
- First-class MCP catalog/executor integration with reusable shared session lifecycle and policy metadata mapping.
- Plug-and-play `AgentWeaveApplication.from_mcp()` / `.from_mcps()` factories, multi-catalog composition, collision-safe aliases, and canonical-key executor dispatch.
- Real MCP in-process server/client end-to-end CI, including two MCP servers exposing the same native tool name.
- First-class LangGraph and AutoGen adapters backed only by the public runtime API.
- Centralized `SafeHttpTransport` across AgentWeave-owned HTTP integrations.
- Typed runtime configuration, builder/factory, versioned plugin component registry, and lifecycle-owned `AgentWeaveApplication`.
- Real upstream MCP, LangGraph, and AutoGen compatibility CI in addition to local test doubles.
- Runtime red-team coverage for malformed JSON, invalid schemas, argument escalation, hidden high-risk tool selection, and execution-gate bypass attempts.
- Routing scale evidence harness covering 100, 1,000, 10,000, and 100,000 tool catalogs with wall-clock latency and Python peak-memory reporting.
- Separate real-provider Issue #38 strategy/ablation harness reporting provider token usage and wall-clock latency without modifying the frozen controlled artifact.
- Built-wheel installation smoke matrix for base, MCP, LangGraph, and AutoGen extras.
- 0.7 quickstart, live-provider protocol documentation, and explicit road-to-1.0 compatibility/release gates.
- Confidence-aware adaptive routing, abstention/deferred search, and the controlled hybrid-selection evaluation.

### Changed
- Distribution name is `agentweave-router`; Python imports remain `agentweave`.
- Public root API is curated; historical root imports remain as pre-1.0 compatibility shims with deprecation warnings.
- Deferred discovery candidates are re-scoped before routing/model exposure.
- Tool execution recovery tracks canonical tool identity rather than display name.
- Runtime and plugin lifecycles are idempotent and fail safely on partial startup.
- Release tags now gate on core tests, supported upstream integrations, real MCP end-to-end proof, distribution validation, and a fresh built-wheel install before GitHub release/PyPI publication.

### Security
- Mandatory Agent Card payload binding and explicit trusted/untrusted registration boundaries.
- Redirect/DNS-rebinding SSRF hardening and cross-origin credential stripping for AgentWeave-owned HTTP traffic.
- Model-hallucinated, schema-invalid, scope-denied, and authorization-denied calls fail closed before the executor.
- Multi-MCP execution is dispatched by canonical tool identity so same-name tools cannot silently cross provider/server boundaries.

## [0.6.0] - 2026-08-25

### Added
- gRPC A2A lifecycle transport over generated protocol stubs.
- A2A task push-notification configuration and authenticated webhook receiver.
- Expanded red-team campaign: malicious Agent Cards, data-exfiltration instructions, SSRF/link-local access, tool abuse, identity spoofing, Sybil/collusion, reputation poisoning, Byzantine disagreement and malformed results.
- Docker cgroup/resource isolation checks and Bubblewrap proof support.
- Verifiable Credential, revocation, key-management boundary, certificate rotation and workload-attestation proof suite.
- PostgreSQL concurrency, reconnect/recovery, write-through replication and audit-durability proof.
- Reliability/chaos suite for disappearing agents, slow agents, network partitions, malformed outputs and database failures.
- Native C++ team-selection bridge and microbenchmark.
- Embedding-only routing baseline, richer team metrics and research-package artifacts.
- Ontology import, RDF/SKOS loading, contradiction relationships and semantic retrieval.
- NLI/source-quality hooks and verification calibration metrics.
- End-to-end in-process trace/audit/selection explanation capture.
- Stronger CLI (`doctor`, `graph-stats`, `plugins`, `version`, `config-check`).
- Release, security, contribution and API-compatibility policies.

### Changed
- Deep-proof workflows publish richer security, storage, research, governance and scale artifacts.
- Project version advanced to 0.6.0.

## [0.5.0] - 2026-08-15

- Added official A2A TCK JSON-RPC conformance proof, 10K scale proof, research baselines, PostgreSQL deployment proof and external/edge proof harnesses.

## [0.4.0] - 2026-08-15

- Added production-oriented trust, marketplace, sandbox, ontology, storage, governance, observability and edge layers.

## [0.3.0] - 2026-08-15

- Hardened result/security validation, signed Agent Cards, executable retesting and native ranking integration.
