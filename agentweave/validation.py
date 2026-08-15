from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import base64, json, hashlib
from typing import Callable, Any
from .models import AgentProfile

@dataclass
class BenchmarkCase:
    capability: str
    prompt: str
    evaluator: Callable[[Any], float]
    weight: float = 1.0

class IdentityVerifier:
    def verify_hash_signature(self,payload:bytes,signature_hex:str,shared_secret:str)->bool:
        expected=hashlib.sha256(shared_secret.encode()+payload).hexdigest()
        ok = expected == signature_hex
        return ok
    def verify_jws(self,token:str,public_key_pem:bytes,algorithms=None)->dict:
        try:
            import jwt
        except ImportError as e:
            raise RuntimeError('Install agentweave[security] for JWS verification') from e
        return jwt.decode(token,public_key_pem,algorithms=algorithms or ['RS256','ES256'],options={'verify_aud':False})

class SecurityValidator:
    def validate(self,agent:AgentProfile):
        problems=[]
        ep=agent.execution.endpoint or ''
        if ep and not (ep.startswith('https://') or ep.startswith('http://localhost') or ep.startswith('http://127.0.0.1')): problems.append('endpoint-not-tls')
        if agent.metadata.get('requires_raw_credentials'): problems.append('raw-credentials-requested')
        if agent.metadata.get('unrestricted_filesystem'): problems.append('unrestricted-filesystem')
        score=max(0.0,1.0-.3*len(problems)); agent.trust.security=score
        return {'passed':score>=.7,'score':score,'problems':problems}

class BenchmarkValidator:
    def __init__(self,invoke): self.invoke=invoke
    async def run(self,agent:AgentProfile,cases:list[BenchmarkCase],threshold=.7):
        by_cap={}
        details=[]
        for case in cases:
            result=await self.invoke(agent,case.prompt)
            score=max(0.0,min(1.0,float(case.evaluator(result))))
            by_cap.setdefault(case.capability,[]).append((score,case.weight)); details.append({'capability':case.capability,'score':score})
        for cap in agent.capabilities:
            vals=by_cap.get(cap.name,[])
            if vals:
                score=sum(s*w for s,w in vals)/sum(w for _,w in vals); cap.proficiency=score; cap.validated=score>=threshold; cap.last_validated_at=datetime.now(timezone.utc).isoformat()
        agent.last_tested_at=datetime.now(timezone.utc).isoformat()
        agent.trust.capability=sum(c.proficiency for c in agent.capabilities)/max(1,len(agent.capabilities))
        return {'passed':any(c.validated for c in agent.capabilities),'details':details}

class ResultValidator:
    def validate(self,results:list[dict],required_capabilities:set[str]):
        good=[r for r in results if r.get('success') and not r.get('response',{}).get('error')]
        coverage=set()
        for r in good: coverage |= set(r.get('matched_capabilities',[]))
        coverage_score=len(coverage & required_capabilities)/max(1,len(required_capabilities))
        evidence_score=sum(1 for r in good if self._has_content(r.get('response')))/max(1,len(good))
        score=.65*coverage_score+.35*evidence_score
        return {'passed':bool(good) and score>=.5,'score':score,'coverage':coverage_score,'usable_results':len(good)}
    def _has_content(self,r):
        if isinstance(r,dict): return any(v not in (None,'',[],{}) for k,v in r.items() if k!='error')
        return bool(r)

class RetestPolicy:
    def __init__(self,max_age_hours=24*30,min_historical=.6): self.max_age_hours=max_age_hours; self.min_historical=min_historical
    def due(self,agent:AgentProfile):
        if agent.trust.historical<self.min_historical or not agent.last_tested_at: return True
        try: dt=datetime.fromisoformat(agent.last_tested_at.replace('Z','+00:00')); return datetime.now(timezone.utc)-dt>timedelta(hours=self.max_age_hours)
        except ValueError: return True
