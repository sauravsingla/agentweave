from __future__ import annotations
import base64, hashlib, json, os, pathlib, time
from dataclasses import dataclass, asdict
from .identity import DIDResolver, VerifiableCredentialVerifier, RevocationRegistry, CertificateRotationManager, KeyManager, WorkloadAttestationVerifier

@dataclass
class IdentityProofResult:
    name: str
    passed: bool
    detail: dict


class IdentityInfrastructureProof:
    """Cryptographic identity proof plus optional live DID/attestation checks."""
    def run_offline(self):
        try:
            import jwt
            from cryptography.hazmat.primitives.asymmetric import ed25519
            from cryptography.hazmat.primitives import serialization
        except ImportError as exc:
            return [IdentityProofResult('security-dependencies', False, {'error': str(exc)})]

        private = ed25519.Ed25519PrivateKey.generate()
        public = private.public_key()
        private_pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        public_pem = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        claims = {
            'iss': 'did:web:issuer.example',
            'sub': 'did:web:agent.example',
            'iat': int(time.time()),
            'vc': {'type': ['VerifiableCredential', 'AgentCapabilityCredential'], 'credentialSubject': {'id': 'did:web:agent.example', 'capability': 'analysis'}},
        }
        token = jwt.encode(claims, private_pem, algorithm='EdDSA')
        verified = VerifiableCredentialVerifier().verify_jwt_vc(token, public_pem, algorithms=['EdDSA'], issuer='did:web:issuer.example')

        revocations = RevocationRegistry()
        revocations.revoke('did:web:agent.example', 'compromised-key')
        revoked = revocations.is_revoked('did:web:agent.example')
        revocations.restore('did:web:agent.example')
        restored = not revocations.is_revoked('did:web:agent.example')

        signer = KeyManager(
            signer=lambda key_id, payload: private.sign(payload),
            verifier=lambda key_id, payload, signature: public.verify(signature, payload) is None,
        )
        payload = b'agentweave-kms-boundary'
        signature = signer.sign('kms://agent/key-1', payload)
        kms_ok = signer.verify('kms://agent/key-1', payload, signature)

        rotation = CertificateRotationManager(max_age_seconds=90 * 86400)
        rotation_ok = rotation.due(time.time() - 91 * 86400) and not rotation.due(time.time() - 10 * 86400)

        evidence = {'timestamp': time.time(), 'nonce': 'n-1', 'measurement': hashlib.sha256(b'workload').hexdigest(), 'issuer': 'test-attestor'}
        attestation = WorkloadAttestationVerifier(verifier=lambda e: e.get('issuer') == 'test-attestor').verify(evidence)

        return [
            IdentityProofResult('signed-verifiable-credential', verified.get('sub') == 'did:web:agent.example', {'subject': verified.get('sub'), 'issuer': verified.get('iss')}),
            IdentityProofResult('revocation-and-restore', revoked and restored, {'revoked': revoked, 'restored': restored}),
            IdentityProofResult('kms-hsm-interface-sign-verify', kms_ok, {'signature_bytes': len(signature)}),
            IdentityProofResult('certificate-rotation-policy', rotation_ok, {'max_age_days': 90}),
            IdentityProofResult('workload-attestation-policy', bool(attestation['passed']), attestation),
        ]

    async def run_live_did(self, did: str | None = None, universal_resolver: str | None = None):
        did = did or os.getenv('AGENTWEAVE_LIVE_DID')
        if not did:
            return IdentityProofResult('live-did-resolution', False, {'error': 'AGENTWEAVE_LIVE_DID not configured'})
        resolver = DIDResolver(universal_resolver or os.getenv('AGENTWEAVE_UNIVERSAL_RESOLVER'))
        document = await resolver.resolve(did)
        passed = document.get('id') == did and bool(document.get('verificationMethod') or document.get('authentication'))
        return IdentityProofResult('live-did-resolution', passed, {'id': document.get('id'), 'verification_methods': len(document.get('verificationMethod', []))})


def write_identity_report(results, path='identity-proof.json'):
    payload = [asdict(x) for x in results]
    pathlib.Path(path).write_text(json.dumps(payload, indent=2))
    return all(x.passed for x in results)
