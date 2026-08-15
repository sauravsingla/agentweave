# AgentWeave

AgentWeave is a domain-agnostic framework for discovering, validating, matching, and orchestrating heterogeneous AI agents across cloud, enterprise, marketplace, and edge environments.

It treats A2A as an interoperability layer and adds the decision layer above it: which agent (or team) should handle a requirement, whether those agents are trustworthy for that requirement, where they should execute, and how performance should update future selection.

## v0.1 capabilities

- Requirement-to-capability decomposition
- Agent registry and marketplace ingestion
- Claimed vs validated capabilities
- Multi-dimensional trust scoring
- Capability-aware ranking
- Complementary team formation
- A2A-style task invocation through pluggable adapters
- Edge/cloud placement metadata and scoring
- Outcome evaluation and reputation updates
- Optional FastAPI service
- Optional C++ scoring core
- Unit tests and end-to-end demo

## Architecture

```text
Requirement
   -> Requirement Analyzer
   -> Capability Ontology
   -> Agent Registry <--- Marketplace / A2A / Edge adapters
   -> Validation + Trust Engine
   -> Matcher + Team Selector
   -> A2A Orchestrator
   -> Result Aggregation
   -> Outcome / Reputation Update
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python examples/demo.py
```

Tests:

```bash
pip install -e .[dev]
pytest -q
```

API:

```bash
pip install -e .[api]
uvicorn agentweave.service:app --reload
```

## Design principles

1. Identity is not competence.
2. Claimed capability is not validated capability.
3. Trust is contextual and multi-dimensional.
4. Complex requirements may need teams, not a single agent.
5. Edge/cloud placement is part of selection.
6. Outcome history should improve future routing.
7. Protocols such as A2A are adapters, not the whole architecture.

## Status

Initial working framework scaffold (v0.1). It is intended for experimentation and extension, not production security certification.

## License

Apache-2.0.
