from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import re

@dataclass
class Capability:
    name: str
    proficiency: float = 0.5
    validated: bool = False

@dataclass
class TrustVector:
    identity: float = 0.5
    capability: float = 0.5
    domain: float = 0.5
    execution: float = 0.5
    collaboration: float = 0.5
    historical: float = 0.5
    def score(self) -> float:
        vals=[self.identity,self.capability,self.domain,self.execution,self.collaboration,self.historical]
        return sum(vals)/len(vals)

@dataclass
class ExecutionProfile:
    location: str = "cloud"
    latency_ms: float = 500.0
    cost: float = 0.0
    offline: bool = False
    privacy_level: str = "standard"
    available: bool = True

@dataclass
class AgentProfile:
    agent_id: str
    name: str
    capabilities: list[Capability]
    domains: list[str] = field(default_factory=list)
    trust: TrustVector = field(default_factory=TrustVector)
    execution: ExecutionProfile = field(default_factory=ExecutionProfile)
    metadata: dict[str,Any] = field(default_factory=dict)
    tasks_completed: int = 0
    tasks_succeeded: int = 0

@dataclass
class Requirement:
    text: str
    capabilities: set[str]
    domains: set[str]=field(default_factory=set)
    local_only: bool=False

@dataclass
class MatchResult:
    agent: AgentProfile
    score: float
    matched_capabilities: set[str]
    missing_capabilities: set[str]

class RequirementAnalyzer:
    ontology={
      "research":{"research","evidence","literature","investigate"},
      "summarization":{"summarize","summary","brief"},
      "analysis":{"analyze","analyse","evaluate","assess"},
      "coding":{"code","program","python","c++","software"},
      "vision":{"image","video","vision","camera"},
      "forecasting":{"forecast","predict","prediction"},
      "optimization":{"optimize","optimise","schedule","routing"},
      "compliance":{"compliance","regulation","policy","legal"},
      "reasoning":{"reason","decision","recommend","plan","solve"}
    }
    def analyze(self,text:str,domains=None,local_only=False)->Requirement:
        tokens=set(re.findall(r"[a-z0-9+.-]+",text.lower()))
        caps={k for k,v in self.ontology.items() if tokens & v} or {"reasoning"}
        local_only=local_only or any(x in text.lower() for x in ("local only","on-device","offline"))
        return Requirement(text,caps,set(domains or []),local_only)

class AgentRegistry:
    def __init__(self): self._agents={}
    def register(self,agent): self._agents[agent.agent_id]=agent; return agent
    def ingest(self,agents):
        for a in agents: self.register(a)
        return len(agents)
    def all(self): return list(self._agents.values())
    def get(self,agent_id): return self._agents.get(agent_id)

class TrustEngine:
    def score(self,agent):
        history=(agent.tasks_succeeded/agent.tasks_completed) if agent.tasks_completed else agent.trust.historical
        return .8*agent.trust.score()+.2*history
    def update(self,agent,success):
        agent.tasks_completed+=1
        agent.tasks_succeeded+=int(bool(success))
        obs=1.0 if success else 0.0
        agent.trust.historical=.85*agent.trust.historical+.15*obs

class ValidationGateway:
    def validate(self,agent,threshold=.7):
        scores={}
        for cap in agent.capabilities:
            scores[cap.name]=cap.proficiency
            cap.validated=cap.proficiency>=threshold
        agent.trust.capability=sum(scores.values())/len(scores) if scores else 0.0
        return {"agent_id":agent.agent_id,"passed":any(c.validated for c in agent.capabilities),"capabilities":scores}

class AgentMatcher:
    def __init__(self,trust=None): self.trust=trust or TrustEngine()
    def match(self,req,agent):
        capmap={c.name.lower():c for c in agent.capabilities}
        matched=req.capabilities & set(capmap)
        missing=req.capabilities-set(capmap)
        if req.local_only and agent.execution.location!="edge": return MatchResult(agent,0.0,matched,missing)
        if not agent.execution.available: return MatchResult(agent,0.0,matched,missing)
        coverage=len(matched)/max(1,len(req.capabilities))
        prof=sum(capmap[c].proficiency for c in matched)/len(matched) if matched else 0.0
        validated=sum(1 for c in matched if capmap[c].validated)/len(matched) if matched else 0.0
        trust=self.trust.score(agent)
        domain=1.0 if not req.domains or req.domains & set(map(str.lower,agent.domains)) else .3
        score=.42*coverage+.22*prof+.12*validated+.16*trust+.08*domain
        return MatchResult(agent,score,matched,missing)
    def rank(self,req,agents): return sorted([self.match(req,a) for a in agents],key=lambda m:m.score,reverse=True)

class TeamSelector:
    def select(self,req,ranked,max_agents=5):
        uncovered=set(req.capabilities); team=[]; pool=list(ranked)
        while uncovered and pool and len(team)<max_agents:
            best=max(pool,key=lambda m:(len(m.matched_capabilities & uncovered),m.score))
            new=best.matched_capabilities & uncovered
            if not new: break
            team.append(best); uncovered-=new; pool.remove(best)
        if not team and ranked and ranked[0].score>0: team=[ranked[0]]
        return team

class StaticMarketplace:
    def __init__(self,agents): self.agents=list(agents)
    def list_agents(self): return list(self.agents)

class PlacementEngine:
    def score(self,req,agent):
        if req.local_only and agent.execution.location!="edge": return 0.0
        locality=1.0 if agent.execution.location=="edge" else .7
        privacy=1.0 if agent.execution.privacy_level in {"local-only","confidential"} else .6
        latency=1/(1+agent.execution.latency_ms/1000)
        return .4*locality+.35*privacy+.25*latency
