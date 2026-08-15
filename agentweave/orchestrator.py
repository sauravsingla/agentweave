from __future__ import annotations
import asyncio
from .core import AgentRegistry, RequirementAnalyzer, TrustEngine, ValidationGateway, AgentMatcher, TeamSelector, PlacementEngine
from .a2a import A2AAdapter, InMemoryA2AAdapter

class AgentWeave:
    def __init__(self, a2a: A2AAdapter | None = None):
        self.registry = AgentRegistry()
        self.analyzer = RequirementAnalyzer()
        self.trust = TrustEngine()
        self.validator = ValidationGateway()
        self.matcher = AgentMatcher(self.trust)
        self.selector = TeamSelector()
        self.placement = PlacementEngine()
        self.a2a = a2a or InMemoryA2AAdapter()

    def ingest_marketplace(self, marketplace, validate: bool = True):
        agents = marketplace.list_agents()
        results = []
        for agent in agents:
            verdict = self.validator.validate(agent) if validate else {"passed": True}
            if verdict.get("passed"):
                self.registry.register(agent)
            results.append(verdict)
        return results

    async def solve(self, text: str, *, domains=None, local_only=False, max_agents=5):
        req = self.analyzer.analyze(text, domains=domains, local_only=local_only)
        ranked = self.matcher.rank(req, self.registry.all())
        team = self.selector.select(req, ranked, max_agents=max_agents)
        if not team:
            return {"status":"no-suitable-agent","requirement":text,"required_capabilities":sorted(req.capabilities),"results":[]}
        async def run(member):
            try:
                response = await self.a2a.invoke(member.agent.agent_id, text)
                success = True
            except Exception as exc:
                response = {"error": str(exc)}
                success = False
            self.trust.update(member.agent, success)
            return {
                "agent_id": member.agent.agent_id,
                "agent_name": member.agent.name,
                "match_score": round(member.score, 4),
                "matched_capabilities": sorted(member.matched_capabilities),
                "response": response,
                "success": success,
            }
        results = await asyncio.gather(*(run(m) for m in team))
        return {
            "status":"completed" if any(r["success"] for r in results) else "failed",
            "requirement": text,
            "required_capabilities": sorted(req.capabilities),
            "selected_agents": [m.agent.agent_id for m in team],
            "results": results,
        }
