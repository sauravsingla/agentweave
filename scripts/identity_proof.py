import asyncio, json, os, pathlib
from dataclasses import asdict
from agentweave.identity_proof import IdentityInfrastructureProof

async def main():
    suite=IdentityInfrastructureProof(); rows=suite.run_offline()
    if os.getenv('AGENTWEAVE_LIVE_DID'):
        rows.append(await suite.run_live_did())
    payload=[asdict(x) for x in rows]
    pathlib.Path('identity-proof.json').write_text(json.dumps(payload,indent=2,default=str))
    print(json.dumps(payload,indent=2,default=str))
    return 0 if all(x.passed for x in rows) else 1

raise SystemExit(asyncio.run(main()))
