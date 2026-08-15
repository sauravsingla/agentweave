"""Backward-compatible imports for AgentWeave core types."""
from .models import *
from .requirements import RequirementAnalyzer
from .engine import AgentRegistry, TrustEngine, PlacementEngine, AgentMatcher, TeamSelector
from .discovery import StaticMarketplace

class ValidationGateway:
    """Compatibility validator; for benchmark validation use BenchmarkValidator."""
    def validate(self,agent,threshold=.7):
        scores={c.name:c.proficiency for c in agent.capabilities}
        for c in agent.capabilities: c.validated=c.proficiency>=threshold
        agent.trust.capability=sum(scores.values())/max(1,len(scores))
        return {'agent_id':agent.agent_id,'passed':any(c.validated for c in agent.capabilities),'capabilities':scores}
