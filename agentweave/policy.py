from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class PolicyContext:
    user:str|None=None
    jurisdiction:str|None=None
    data_residency:str|None=None
    risk_tier:str='standard'
    allowed_tools:set[str]=field(default_factory=set)
    human_approved:bool=False

@dataclass
class PolicyDecision:
    allowed:bool
    reasons:list[str]
    requires_human:bool=False

class GovernancePolicyEngine:
    def __init__(self,allowed_jurisdictions=None,allowed_residencies=None,blocked_tools=None,human_approval_tiers=None):
        self.allowed_jurisdictions=set(allowed_jurisdictions or []); self.allowed_residencies=set(allowed_residencies or []); self.blocked_tools=set(blocked_tools or []); self.human_tiers=set(human_approval_tiers or {'high','critical'})
    def evaluate(self,agent,req,context:PolicyContext|None=None):
        context=context or PolicyContext(); reasons=[]; needs_human=context.risk_tier in self.human_tiers
        if self.allowed_jurisdictions and context.jurisdiction not in self.allowed_jurisdictions: reasons.append('jurisdiction-not-allowed')
        if self.allowed_residencies and context.data_residency not in self.allowed_residencies: reasons.append('data-residency-not-allowed')
        requested=set(agent.metadata.get('tools',[])); blocked=requested & self.blocked_tools
        if blocked: reasons.append('blocked-tools:'+','.join(sorted(blocked)))
        if context.allowed_tools and not requested.issubset(context.allowed_tools): reasons.append('tool-not-authorized')
        if needs_human and not context.human_approved: reasons.append('human-approval-required')
        if getattr(req,'local_only',False) and agent.execution.location!='edge': reasons.append('locality-policy-failed')
        return PolicyDecision(not reasons,reasons,needs_human)

class PolicyFilteredRegistry:
    def __init__(self,registry,engine): self.registry=registry; self.engine=engine
    def candidates(self,req,context=None): return [a for a in self.registry.all() if self.engine.evaluate(a,req,context).allowed]
