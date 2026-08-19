from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agentweave import (
    AgentProfile,
    AgentWeave,
    Capability,
    ExecutionProfile,
    TrustVector,
)


class RoutingState(TypedDict, total=False):
    query: str
    selected_agents: list[str]
    required_capabilities: list[str]
    selection_explanation: dict
    result: str


def make_agent(agent_id: str, name: str, capabilities: list[str]) -> AgentProfile:
    return AgentProfile(
        agent_id=agent_id,
        name=name,
        capabilities=[
            Capability(name=capability, proficiency=0.9, validated=True)
            for capability in capabilities
        ],
        trust=TrustVector(
            identity=0.9,
            capability=0.9,
            domain=0.9,
            execution=0.9,
            security=0.9,
            collaboration=0.9,
            historical=0.9,
        ),
        execution=ExecutionProfile(
            location="local",
            latency_ms=20,
            cost=0.0,
            privacy_level="confidential",
        ),
    )


def build_agentweave() -> AgentWeave:
    weave = AgentWeave(db_path=":memory:", use_native=False)
    weave.register(make_agent("researcher", "Research Agent", ["research", "reasoning"]))
    weave.register(make_agent("coder", "Coding Agent", ["coding", "reasoning"]))
    weave.register(make_agent("policy", "Policy Agent", ["compliance", "reasoning"]))
    return weave


WEAVE = build_agentweave()


def route_with_agentweave(state: RoutingState) -> RoutingState:
    """Use AgentWeave as a LangGraph routing node.

    This node performs requirement analysis, policy filtering, ranking, team selection,
    and structured selection explanation. It does not call an LLM.
    """
    query = state["query"]
    req = WEAVE.analyzer.analyze(query)

    candidates = []
    policy_decisions = {}
    for agent in WEAVE.registry.all():
        decision = WEAVE.policy.evaluate(agent, req)
        policy_decisions[agent.agent_id] = decision.__dict__
        if decision.allowed and not WEAVE.revocations.is_revoked(agent.agent_id):
            candidates.append(agent)

    ranked = WEAVE.matcher.rank(req, candidates)
    team = WEAVE.selector.select(req, ranked, max_agents=2)
    explanation = WEAVE.observability.explainer.explain(
        req, ranked, team, policy_decisions
    )

    return {
        "required_capabilities": sorted(req.capabilities),
        "selected_agents": [member.agent.agent_id for member in team],
        "selection_explanation": explanation,
    }


def downstream_work(state: RoutingState) -> RoutingState:
    """Stand-in for normal LangGraph downstream work.

    In a real graph, replace this node with model/tool/agent execution.
    """
    selected = state.get("selected_agents", [])
    return {
        "result": (
            "LangGraph would continue with: " + ", ".join(selected)
            if selected
            else "No suitable AgentWeave route was found."
        )
    }


def build_graph():
    graph = StateGraph(RoutingState)
    graph.add_node("agentweave_route", route_with_agentweave)
    graph.add_node("downstream_work", downstream_work)
    graph.add_edge(START, "agentweave_route")
    graph.add_edge("agentweave_route", "downstream_work")
    graph.add_edge("downstream_work", END)
    return graph.compile()


if __name__ == "__main__":
    app = build_graph()
    output = app.invoke({"query": "Analyze this policy and recommend a compliant plan"})
    print("Required capabilities:", output["required_capabilities"])
    print("Selected agents:", output["selected_agents"])
    print(output["result"])
