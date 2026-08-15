from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import asyncio
import hashlib
import hmac
import ipaddress
import json
import socket
from typing import Callable, Any, Awaitable
from urllib.parse import urlparse
from .models import AgentProfile

@dataclass
class BenchmarkCase:
    capability: str
    prompt: str
    evaluator: Callable[[Any], float]
    weight: float = 1.0
    timeout_seconds: float = 30.0

class IdentityVerifier:
    """Cryptographic identity helpers for agent metadata and Agent Cards."""
    def verify_hash_signature(self,payload:bytes,signature_hex:str,shared_secret:str)->bool:
        expected=hmac.new(shared_secret.encode(),payload,hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected,signature_hex)

    def verify_jws(self,token:str,public_key_pem:bytes,algorithms=None,*,audience=None,issuer=None)->dict:
        try:
            import jwt
        except ImportError as e:
            raise RuntimeError('Install agentweave[security] for JWS verification') from e
        options={'verify_aud': audience is not None}
        return jwt.decode(token,public_key_pem,algorithms=algorithms or ['RS256','ES256','EdDSA'],audience=audience,issuer=issuer,options=options)

    def canonical_agent_card(self,card:dict)->bytes:
        unsigned={k:v for k,v in card.items() if k not in {'signature','jws'}}
        return json.dumps(unsigned,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()

    def verify_agent_card_jws(self,card:dict,public_key_pem:bytes,*,audience=None,issuer=None)->dict:
        token=card.get('jws') or card.get('signature')
        if not token: raise ValueError('Agent Card has no JWS signature')
        claims=self.verify_jws(token,public_key_pem,audience=audience,issuer=issuer)
        digest=hashlib.sha256(self.canonical_agent_card(card)).hexdigest()
        claimed=claims.get('card_sha256') or claims.get('sha256')
        if claimed and not hmac.compare_digest(str(claimed),digest):
            raise ValueError('Agent Card signature digest does not match card content')
        return claims

class SecurityValidator:
    """Pre-registration security posture checks.

    These checks reject unsafe endpoints/metadata but are not a replacement for OS,
    network or container isolation.
    """
    ALLOWED_BINDINGS={'JSONRPC','HTTP+JSON','HTTP_JSON','REST','LOCAL','EDGE'}
    def __init__(self,*,allow_private_network=False,allowed_hosts=None,require_tls=True,attestation_verifier:Callable[[AgentProfile],bool]|None=None):
        self.allow_private_network=allow_private_network
        self.allowed_hosts=set(allowed_hosts or [])
        self.require_tls=require_tls
        self.attestation_verifier=attestation_verifier

    def _host_is_private(self,host:str)->bool:
        if host in {'localhost','127.0.0.1','::1'}: return True
        try:
            ips={ipaddress.ip_address(host)}
        except ValueError:
            try: ips={ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)}
            except (socket.gaierror,ValueError): return False
        return any(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved for ip in ips)

    def validate(self,agent:AgentProfile):
        problems=[]; warnings=[]
        ep=agent.execution.endpoint or ''
        if ep:
            parsed=urlparse(ep)
            if parsed.scheme not in {'https','http'}: problems.append('unsupported-endpoint-scheme')
            if self.require_tls and parsed.scheme!='https' and parsed.hostname not in {'localhost','127.0.0.1','::1'}: problems.append('endpoint-not-tls')
            if not parsed.hostname: problems.append('endpoint-missing-host')
            elif self.allowed_hosts and parsed.hostname not in self.allowed_hosts: problems.append('host-not-allowlisted')
            elif not self.allow_private_network and parsed.hostname not in {'localhost','127.0.0.1','::1'} and self._host_is_private(parsed.hostname): problems.append('private-network-endpoint')
            if parsed.username or parsed.password: problems.append('credentials-in-url')
        binding=str(agent.metadata.get('protocol_binding') or agent.metadata.get('agent_card',{}).get('protocolBinding') or 'JSONRPC').upper()
        if binding not in self.ALLOWED_BINDINGS: problems.append('unsupported-protocol-binding')
        if agent.metadata.get('requires_raw_credentials'): problems.append('raw-credentials-requested')
        if agent.metadata.get('unrestricted_filesystem'): problems.append('unrestricted-filesystem')
        if agent.metadata.get('shell_access'): problems.append('shell-access-requested')
        if agent.metadata.get('disable_tls_verify'): problems.append('tls-verification-disabled')
        scopes=agent.metadata.get('requested_scopes',[]) or []
        if any(str(s).lower() in {'admin','root','*','all'} for s in scopes): problems.append('overbroad-scope')
        if not agent.metadata.get('agent_card') and ep: warnings.append('agent-card-not-cached')
        if self.attestation_verifier is not None:
            try:
                if not self.attestation_verifier(agent): problems.append('attestation-failed')
            except Exception: problems.append('attestation-error')
        score=max(0.0,1.0-.22*len(problems)-.03*len(warnings)); agent.trust.security=score
        return {'passed':not problems and score>=.7,'score':score,'problems':problems,'warnings':warnings,'binding':binding}

class BenchmarkValidator:
    def __init__(self,invoke): self.invoke=invoke
    async def run(self,agent:AgentProfile,cases:list[BenchmarkCase],threshold=.7):
        by_cap={}; details=[]
        for case in cases:
            try:
                result=await asyncio.wait_for(self.invoke(agent,case.prompt),timeout=case.timeout_seconds)
                score=max(0.0,min(1.0,float(case.evaluator(result))))
                error=None
            except Exception as exc:
                score=0.0; error=str(exc)
            by_cap.setdefault(case.capability.lower(),[]).append((score,case.weight))
            details.append({'capability':case.capability,'score':score,'weight':case.weight,'error':error})
        now=datetime.now(timezone.utc).isoformat()
        for cap in agent.capabilities:
            vals=by_cap.get(cap.name.lower(),[])
            if vals:
                denom=sum(max(0.0,w) for _,w in vals) or 1.0
                score=sum(s*max(0.0,w) for s,w in vals)/denom
                cap.proficiency=score; cap.validated=score>=threshold; cap.last_validated_at=now
        agent.last_tested_at=now
        agent.trust.capability=sum(c.proficiency for c in agent.capabilities)/max(1,len(agent.capabilities))
        tested=[c for c in agent.capabilities if c.name.lower() in by_cap]
        return {'passed':bool(tested) and all(c.validated for c in tested),'details':details,'tested_capabilities':[c.name for c in tested]}

class ResultValidator:
    """Composite result quality validation with extensible semantic/evidence hooks."""
    def __init__(self,*,semantic_evaluator:Callable[[dict],float]|None=None,evidence_evaluator:Callable[[dict],float]|None=None,min_score=.60):
        self.semantic_evaluator=semantic_evaluator; self.evidence_evaluator=evidence_evaluator; self.min_score=min_score

    def _has_content(self,r):
        if isinstance(r,dict): return any(v not in (None,'',[],{}) for k,v in r.items() if k!='error')
        return bool(r)

    def _extract_answer(self,response):
        if isinstance(response,dict):
            for k in ('decision','answer','result','output','text','content'):
                if k in response and response[k] not in (None,''): return response[k]
        return response

    def _normalize(self,value):
        if isinstance(value,(dict,list)): return json.dumps(value,sort_keys=True,default=str).strip().lower()
        return ' '.join(str(value).strip().lower().split())

    def validate(self,results:list[dict],required_capabilities:set[str],*,consensus:dict|None=None):
        good=[r for r in results if r.get('success') and not (isinstance(r.get('response'),dict) and r.get('response',{}).get('error'))]
        coverage=set()
        for r in good: coverage |= {str(x).lower() for x in r.get('matched_capabilities',[])}
        required={str(x).lower() for x in required_capabilities}
        coverage_score=len(coverage & required)/max(1,len(required))
        content_score=sum(1 for r in good if self._has_content(r.get('response')))/max(1,len(good))
        answers=[self._normalize(self._extract_answer(r.get('response'))) for r in good if self._has_content(r.get('response'))]
        consistency_score=1.0
        if len(answers)>1:
            counts={a:answers.count(a) for a in set(answers)}; consistency_score=max(counts.values())/len(answers)
        if consensus and consensus.get('agreement') is not None: consistency_score=max(consistency_score,float(consensus['agreement']))
        evidence_values=[]; semantic_values=[]
        for r in good:
            if self.evidence_evaluator:
                try: evidence_values.append(max(0.0,min(1.0,float(self.evidence_evaluator(r)))))
                except Exception: evidence_values.append(0.0)
            else:
                resp=r.get('response',{}); evidence_values.append(1.0 if isinstance(resp,dict) and any(k in resp for k in ('evidence','sources','citations','provenance')) else .5)
            if self.semantic_evaluator:
                try: semantic_values.append(max(0.0,min(1.0,float(self.semantic_evaluator(r)))))
                except Exception: semantic_values.append(0.0)
            else: semantic_values.append(1.0 if self._has_content(r.get('response')) else 0.0)
        evidence_score=sum(evidence_values)/max(1,len(evidence_values)); semantic_score=sum(semantic_values)/max(1,len(semantic_values))
        score=.28*coverage_score+.20*content_score+.18*consistency_score+.16*evidence_score+.18*semantic_score
        issues=[]
        if not good: issues.append('no-usable-results')
        if coverage_score<1.0: issues.append('incomplete-capability-coverage')
        if consistency_score<.6 and len(good)>1: issues.append('low-cross-agent-consistency')
        if evidence_score<.5: issues.append('weak-evidence')
        return {'passed':bool(good) and score>=self.min_score,'score':score,'coverage':coverage_score,'content':content_score,'consistency':consistency_score,'evidence':evidence_score,'semantic':semantic_score,'usable_results':len(good),'issues':issues}

class RetestPolicy:
    def __init__(self,max_age_hours=24*30,min_historical=.6,min_security=.7): self.max_age_hours=max_age_hours; self.min_historical=min_historical; self.min_security=min_security
    def due(self,agent:AgentProfile):
        if agent.trust.historical<self.min_historical or agent.trust.security<self.min_security or not agent.last_tested_at: return True
        try:
            dt=datetime.fromisoformat(agent.last_tested_at.replace('Z','+00:00'))
            return datetime.now(timezone.utc)-dt>timedelta(hours=self.max_age_hours)
        except ValueError: return True

class RetestManager:
    """Executes due re-tests instead of merely reporting that a re-test is due."""
    def __init__(self,policy:RetestPolicy,benchmark_factory:Callable[[AgentProfile],list[BenchmarkCase]]):
        self.policy=policy; self.benchmark_factory=benchmark_factory
    async def run_due(self,agents:list[AgentProfile],validator:BenchmarkValidator,threshold=.7):
        results={}
        for agent in agents:
            if not self.policy.due(agent): continue
            cases=self.benchmark_factory(agent) or []
            if not cases:
                results[agent.agent_id]={'passed':False,'skipped':True,'reason':'no-benchmark-cases'}; continue
            results[agent.agent_id]=await validator.run(agent,cases,threshold)
        return results
