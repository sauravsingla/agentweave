from __future__ import annotations
import base64, hashlib, json, ssl, time
from dataclasses import dataclass
from urllib.parse import urlparse
import httpx

class DIDResolver:
    """DID resolver with native did:web support and pluggable universal resolver."""
    def __init__(self,universal_resolver_url:str|None=None): self.universal=universal_resolver_url
    async def resolve(self,did:str):
        if did.startswith('did:web:'):
            parts=did.split(':')[2:]; host=parts[0]; path='/'.join(parts[1:])
            url=f'https://{host}/{path}/did.json' if path else f'https://{host}/.well-known/did.json'
            async with httpx.AsyncClient(timeout=15,follow_redirects=True) as c:
                r=await c.get(url); r.raise_for_status(); return r.json()
        if self.universal:
            async with httpx.AsyncClient(timeout=15) as c:
                r=await c.get(self.universal.rstrip('/')+'/1.0/identifiers/'+did); r.raise_for_status(); data=r.json(); return data.get('didDocument',data)
        raise ValueError(f'No resolver configured for {did}')

class VerifiableCredentialVerifier:
    def verify_jwt_vc(self,token:str,key,algorithms=None,audience=None,issuer=None):
        try: import jwt
        except ImportError as exc: raise RuntimeError('Install agentweave[security]') from exc
        claims=jwt.decode(token,key,algorithms=algorithms or ['ES256','RS256','EdDSA'],audience=audience,issuer=issuer,options={'verify_aud':audience is not None})
        if 'vc' not in claims and claims.get('type')!='VerifiableCredential': raise ValueError('not-a-verifiable-credential')
        return claims

@dataclass
class RevocationEntry:
    subject: str
    reason: str
    revoked_at: float

class RevocationRegistry:
    def __init__(self): self._entries={}
    def revoke(self,subject,reason='revoked'): self._entries[subject]=RevocationEntry(subject,reason,time.time())
    def restore(self,subject): self._entries.pop(subject,None)
    def is_revoked(self,subject): return subject in self._entries
    def entry(self,subject): return self._entries.get(subject)

class CertificateRotationManager:
    def __init__(self,max_age_seconds=90*86400): self.max_age=max_age_seconds
    def fingerprint(self,pem:bytes):
        der=ssl.PEM_cert_to_DER_cert(pem.decode()); return hashlib.sha256(base64.b64decode(der)).hexdigest()
    def due(self,issued_at:float,now=None): return (now or time.time())-issued_at>=self.max_age

class KeyManager:
    """Abstracts external KMS/HSM providers; the framework never needs raw private keys."""
    def __init__(self,signer=None,verifier=None): self.signer=signer; self.verifier=verifier
    def sign(self,key_id:str,payload:bytes):
        if not self.signer: raise RuntimeError('No KMS signer configured')
        return self.signer(key_id,payload)
    def verify(self,key_id:str,payload:bytes,signature:bytes):
        if not self.verifier: raise RuntimeError('No KMS verifier configured')
        return bool(self.verifier(key_id,payload,signature))

class WorkloadAttestationVerifier:
    """Verifier for signed workload/hardware attestation envelopes.

    Vendor-specific TPM/TEE verification is supplied as a callback so evidence can
    be checked by TPM, SPIFFE/SPIRE, cloud confidential-compute or HSM services.
    """
    def __init__(self,verifier=None,max_age_seconds=300): self.verifier=verifier; self.max_age=max_age_seconds
    def verify(self,evidence:dict):
        ts=float(evidence.get('timestamp',0)); fresh=abs(time.time()-ts)<=self.max_age
        nonce=bool(evidence.get('nonce')); measurement=bool(evidence.get('measurement'))
        external=True if self.verifier is None else bool(self.verifier(evidence))
        return {'passed':fresh and nonce and measurement and external,'fresh':fresh,'nonce':nonce,'measurement':measurement,'external_verified':external}
