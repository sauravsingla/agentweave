# AgentWeave

AgentWeave is a domain-agnostic framework for discovering, validating, selecting, and orchestrating heterogeneous AI agents across cloud, marketplace, enterprise, and edge environments. It treats A2A as an interoperability layer while adding requirement-aware capability matching, trust, team formation, collaboration, result validation, and outcome-driven reputation.

## Architecture

```text
Cloud Agents ─┐
Marketplace ──┼─> Registry -> Validation -> Capability/Knowledge Graph
Edge LLMs ────┘                         -> Trust Engine
                                         -> Matching/Ranking
                                         -> Team Formation
                                         -> A2A Collaboration
                                         -> Consensus/Conflict Resolution
                                         -> Result Validation
                                         -> Reputation Update
```

## Implemented

- Requirement analysis and capability extraction
- Agent registry with SQLite persistence
- Capability and knowledge graph using NetworkX
- Generic HTTP marketplace adapter plus static marketplace for tests
- Agent Card discovery over HTTP
- Security checks and optional JWS verification
- Benchmark-based capability validation
- Multi-dimensional trust and outcome history
- Requirement-to-agent matching and edge/cloud placement scoring
- Complementary team formation
- A2A JSON-RPC HTTP transport adapter plus in-memory test adapter
- Multi-round agent collaboration
- Consensus detection and arbiter-based conflict resolution
- Result quality/coverage validation
- Persistent reputation updates and re-test policy
- Edge execution adapters for Ollama and llama.cpp
- Optional C++ ranking/team-selection core for high-throughput workloads

## Install

```bash
python -m pip install -e '.[dev,security]'
pytest
```

## Minimal example

```python
import asyncio
from agentweave import AgentWeave, AgentProfile, Capability, InMemoryA2AAdapter

async def main():
    bus = InMemoryA2AAdapter()
    weave = AgentWeave(a2a=bus, db_path=':memory:')

    agent = AgentProfile('research-1', 'Research Agent', [Capability('research', .9, True)])
    weave.registry.register(agent)
    bus.register_handler('research-1', lambda task: {'result': 'evidence-backed finding'})

    result = await weave.solve('Research the topic and summarize evidence', rounds=1)
    print(result)

asyncio.run(main())
```

## Marketplace and external agents

`HttpMarketplace` expects an endpoint that returns either a JSON array or `{ "agents": [...] }`. `AgentCardDiscovery` can ingest a remote agent card into an `AgentProfile`. External agents should be validated before sensitive production use.

## Edge

Edge agents can use `OllamaRuntime` or `LlamaCppRuntime`. Set the agent execution location to `edge` and provide the corresponding model metadata. Local-only requirements will exclude non-edge agents.

## Security model

AgentWeave does not equate identity with competence. Identity/signature verification, transport/security posture, benchmarked capability, domain fit, execution reliability, and historical outcomes are kept as separate signals. Newly discovered marketplace agents should be tested with controlled/synthetic data before access to sensitive contexts.

## C++ acceleration

The `cpp/` module provides native scoring and greedy complementary team selection. It is optional; Python remains the control plane and can use the native core where scale/latency requires it.

## Status

AgentWeave is an experimental open-source framework. External marketplace schemas, A2A endpoints, identity infrastructures, and edge runtimes vary; adapters are intentionally pluggable. Production deployments should add organization-specific authorization, sandboxing, secrets management, observability, and policy enforcement.

## License

Apache-2.0
