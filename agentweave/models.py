from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass
class Capability:
    name: str
    proficiency: float = 0.5
    validated: bool = False
    evidence: list[str] = field(default_factory=list)
    last_validated_at: str | None = None

@dataclass
class TrustVector:
    identity: float = 0.5
    capability: float = 0.5
    domain: float = 0.5
    execution: float = 0.5
    security: float = 0.5
    collaboration: float = 0.5
    historical: float = 0.5
    def score(self) -> float:
        vals = [self.identity,self.capability,self.domain,self.execution,self.security,self.collaboration,self.historical]
        return sum(vals)/len(vals)

@dataclass
class ExecutionProfile:
    location: str = 'cloud'
    latency_ms: float = 500.0
    cost: float = 0.0
    offline: bool = False
    privacy_level: str = 'standard'
    available: bool = True
    runtime: str | None = None
    endpoint: str | None = None
    memory_mb: int | None = None
    metadata: dict[str,Any] = field(default_factory=dict)

@dataclass
class AgentProfile:
    agent_id: str
    name: str
    capabilities: list[Capability]
    domains: list[str] = field(default_factory=list)
    knowledge: list[str] = field(default_factory=list)
    trust: TrustVector = field(default_factory=TrustVector)
    execution: ExecutionProfile = field(default_factory=ExecutionProfile)
    metadata: dict[str,Any] = field(default_factory=dict)
    tasks_completed: int = 0
    tasks_succeeded: int = 0
    signature_verified: bool = False
    last_tested_at: str | None = None
    def to_dict(self): return asdict(self)

@dataclass
class Requirement:
    text: str
    capabilities: set[str]
    domains: set[str] = field(default_factory=set)
    knowledge: set[str] = field(default_factory=set)
    local_only: bool = False
    max_latency_ms: float | None = None
    privacy_level: str | None = None

@dataclass
class MatchResult:
    agent: AgentProfile
    score: float
    matched_capabilities: set[str]
    missing_capabilities: set[str]
    placement_score: float = 0.0
