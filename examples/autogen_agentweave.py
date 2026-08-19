from __future__ import annotations

import asyncio
from typing import Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import CancellationToken

from agentweave.engine import AgentMatcher, PlacementEngine, TrustEngine
from agentweave.models import AgentProfile, Capability, ExecutionProfile, TrustVector
from agentweave.observability import SelectionExplainer
from agentweave.optimizer import GlobalTeamOptimizer
from agentweave.requirements import RequirementAnalyzer


class SpecialistAgent(BaseChatAgent):
    """Small deterministic AutoGen agent used to demonstrate the integration boundary."""

    def __init__(self, name: str, description: str) -> None:
        super().__init__(name=name, description=description)

    @property
    def produced_message_types(self) -> Sequence[type[BaseChatMessage]]:
        return (TextMessage,)

    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:
        task = ""
        for message in reversed(messages):
            if isinstance(message, TextMessage):
                task = str(message.content)
                break
        return Response(
            chat_message=TextMessage(
                source=self.name,
                content=f"{self.name} received the routed task: {task}",
            )
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        return None


def _profile(agent_id: str, name: str, capabilities: list[str]) -> AgentProfile:
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
            latency_ms=10,
            cost=0.0,
            available=True,
        ),
    )


def route_autogen_participants(task: str):
    """Use AgentWeave to choose which AutoGen specialists should enter the team."""

    analyzer = RequirementAnalyzer()
    trust = TrustEngine()
    placement = PlacementEngine()
    matcher = AgentMatcher(trust, placement, use_native=False)
    selector = GlobalTeamOptimizer()
    explainer = SelectionExplainer()

    profiles = [
        _profile(
            "autogen:backend",
            "backend_specialist",
            ["backend", "api", "coding", "reasoning"],
        ),
        _profile(
            "autogen:database",
            "database_specialist",
            ["database", "sql", "reasoning"],
        ),
        _profile(
            "autogen:research",
            "research_specialist",
            ["research", "analysis", "summarization", "reasoning"],
        ),
        _profile(
            "autogen:mcp",
            "mcp_specialist",
            ["mcp", "tool-use", "integration", "reasoning"],
        ),
    ]

    req = analyzer.analyze(task)
    ranked = matcher.rank(req, profiles)
    selected = selector.select(req, ranked, max_agents=2)
    explanation = explainer.explain(req, ranked, selected)

    selected_names = [row.agent.name for row in selected]
    return selected_names, explanation


async def main() -> None:
    task = "Review this backend API design and database query strategy."

    selected_names, explanation = route_autogen_participants(task)

    all_autogen_agents = {
        "backend_specialist": SpecialistAgent(
            "backend_specialist",
            "Reviews backend services, APIs, and application architecture.",
        ),
        "database_specialist": SpecialistAgent(
            "database_specialist",
            "Reviews databases, SQL, schemas, and query design.",
        ),
        "research_specialist": SpecialistAgent(
            "research_specialist",
            "Handles research, analysis, and summarization tasks.",
        ),
        "mcp_specialist": SpecialistAgent(
            "mcp_specialist",
            "Handles MCP, tool-use, and integration questions.",
        ),
    }

    selected_agents = [all_autogen_agents[name] for name in selected_names]
    team = RoundRobinGroupChat(selected_agents, max_turns=max(1, len(selected_agents)))
    result = await team.run(task=task)

    print("AgentWeave selected AutoGen participants:", selected_names)
    print("Selection explanation:", explanation)
    print("AutoGen messages:")
    for message in result.messages:
        source = getattr(message, "source", "unknown")
        content = getattr(message, "content", "")
        print(f"- {source}: {content}")


if __name__ == "__main__":
    asyncio.run(main())
