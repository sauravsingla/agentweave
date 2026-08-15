from __future__ import annotations
import json, os, pathlib, subprocess, tempfile, time
from dataclasses import dataclass, asdict
from .sandbox import DockerSandbox, SandboxLimits
from .benchmarks import AdversarialTestSuite, AdversarialAgent

@dataclass
class SecurityProof:
    name: str
    passed: bool
    detail: dict

class SandboxValidationSuite:
    """Actively verifies network, filesystem, secret and resource isolation."""
    def __init__(self,sandbox=None,image=None):
        self.sandbox=sandbox or DockerSandbox(); self.image=image or os.getenv('AGENTWEAVE_SANDBOX_IMAGE','python:3.11-alpine')

    def run(self):
        if not self.sandbox.available: return [SecurityProof('docker-available',False,{'error':'docker unavailable'})]
        limits=SandboxLimits(memory_mb=128,cpus=.5,pids=32,timeout_seconds=20,network='none',read_only=True,tmpfs_mb=16)
        cases=[
            ('filesystem-readonly',['sh','-lc','touch /blocked'],False),
            ('tmpfs-writable',['sh','-lc','touch /tmp/ok && test -f /tmp/ok'],True),
            ('network-isolated',['sh','-lc','wget -q -T 2 -O- https://example.com >/dev/null'],False),
            ('secret-isolated',['sh','-lc','test -z "$SHOULD_NOT_LEAK"'],True),
        ]
        out=[]
        for name,cmd,expect_success in cases:
            r=self.sandbox.run(self.image,cmd,limits=limits,env={'SHOULD_NOT_LEAK':'top-secret'},allowed_secrets=set())
            observed=bool(r['success']); out.append(SecurityProof(name,observed==expect_success,{'expected_success':expect_success,'observed_success':observed,'returncode':r['returncode'],'stderr':r['stderr'][-500:]}))
        return out

class AdversarialValidationSuite:
    """Deterministic adversarial cases for metadata injection, Sybil groups and poisoned trust."""
    def __init__(self): self.suite=AdversarialTestSuite()
    def run(self):
        from .models import AgentProfile, Capability
        base=AgentProfile('evil','Evil',[Capability('analysis')])
        card=AdversarialAgent.lying_card(base).metadata['agent_card']
        injection=self.suite.sanitize_agent_card(card)
        sybils=AdversarialAgent.sybil_cluster('operator-x',5)
        groups=self.suite.detect_sybil(sybils)
        poisoned=AdversarialAgent.poison_reputation(AgentProfile('poison','Poison',[Capability('analysis')]))
        return [
            SecurityProof('agent-card-prompt-injection',not injection['passed'],injection),
            SecurityProof('sybil-cluster-detection','operator-x' in groups,{'groups':groups}),
            SecurityProof('poisoned-reputation-fixture',poisoned.trust.historical==1.0,{'historical':poisoned.trust.historical,'tasks_completed':poisoned.tasks_completed}),
        ]

def render_security_report(results,path='security-report.json'):
    payload=[asdict(x) for x in results]; pathlib.Path(path).write_text(json.dumps(payload,indent=2)); return all(x.passed for x in results)
