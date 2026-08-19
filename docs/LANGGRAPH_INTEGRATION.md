# LangGraph integration example

This example shows how to use AgentWeave as a routing node inside a LangGraph workflow.

The boundary is:

```text
LangGraph state
    ↓
AgentWeave requirement analysis + policy filtering + ranking + team selection
    ↓
selected agent IDs + structured selection explanation
    ↓
normal LangGraph downstream nodes
```

The example is intentionally local and keyless. It does not call an LLM or an external API. Its purpose is to demonstrate the orchestration boundary cleanly.

## What it demonstrates

`examples/langgraph_agentweave.py` builds a small `StateGraph` with two nodes:

1. `agentweave_route` uses AgentWeave to analyze the request, apply policy filtering, rank candidates, choose a small team, and return a structured explanation.
2. `downstream_work` represents whatever the LangGraph application normally does next: call a model, execute tools, invoke agents, branch, checkpoint, or continue a longer workflow.

This follows LangGraph's normal graph pattern: state enters a node, the node returns a state update, and edges determine what runs next.

## Run it

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -U langgraph
python examples/langgraph_agentweave.py
```

No API key is required.

## Real application wiring

In a production LangGraph application, the routing node can sit before expensive model or agent execution:

```text
START
  ↓
AgentWeave route
  ↓
selected specialist(s)
  ↓
model / tool / agent nodes
  ↓
END or next workflow state
```

The selected agent IDs can be used to choose a subgraph, select a tool family, dispatch to remote A2A agents, or populate model-visible capabilities.

AgentWeave's selection explanation can also be retained in LangGraph state for later debugging or audit use.

## Why this integration is useful

LangGraph provides low-level stateful workflow orchestration. AgentWeave can provide a separate capability-, trust-, policy-, and execution-aware routing decision before the graph continues.

That separation lets the graph own workflow state and control flow while AgentWeave owns specialist selection.

## Evidence boundary

This is an ecosystem integration example, not a benchmark result. It does not imply official LangGraph/LangChain endorsement, and it does not change any frozen AgentWeave research result or BFCL-derived study.
