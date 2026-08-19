# AutoGen integration example

AgentWeave can be used as a **pre-team routing layer** for AutoGen AgentChat.

The integration boundary is:

```text
user task
    ↓
AgentWeave requirement analysis + ranking + team selection
    ↓
selected AutoGen participants
    ↓
normal AutoGen team execution
```

This pattern keeps AutoGen responsible for agent execution and conversation while AgentWeave decides which specialists should enter the team for a particular task.

## What the example demonstrates

[`examples/autogen_agentweave.py`](../examples/autogen_agentweave.py) creates four AutoGen specialists:

- backend specialist;
- database specialist;
- research specialist;
- MCP specialist.

For each task, AgentWeave:

1. infers the task requirements;
2. ranks the available specialist profiles;
3. selects a bounded team;
4. produces a structured selection explanation;
5. passes only the selected specialists into an AutoGen `RoundRobinGroupChat`.

The example uses AutoGen's current `BaseChatAgent` and `RoundRobinGroupChat` APIs. The specialist agents are deliberately deterministic, so the example can be run without an API key or model service.

## Run it

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -U autogen-agentchat
python examples/autogen_agentweave.py
```

AutoGen AgentChat currently requires Python 3.10 or later; AgentWeave itself requires Python 3.11 or later, so Python 3.11+ satisfies both.

## Production pattern

In a real AutoGen application, replace the deterministic `SpecialistAgent` objects with your normal `AssistantAgent`, custom AgentChat agents, or teams.

The routing step remains the same:

```python
selected_names, explanation = route_autogen_participants(task)
selected_agents = [all_autogen_agents[name] for name in selected_names]
team = RoundRobinGroupChat(selected_agents, max_turns=...)
result = await team.run(task=task)
```

This means an application can maintain a large catalog of AutoGen specialists while constructing a smaller task-specific team before conversation begins.

## Why keep the selection explanation?

The returned AgentWeave explanation records which candidates were considered, which were selected, capability matches/misses, scores, and other selection information. That makes it easier to distinguish orchestration decisions from downstream AutoGen behavior.

For tool-level routing provenance, see [Issue #22](../issues/22).

## Evidence and ecosystem boundary

This is an **integration example**, not a benchmark result. It does not modify AutoGen, does not imply Microsoft or AutoGen endorsement, and does not alter any frozen AgentWeave research evidence.
