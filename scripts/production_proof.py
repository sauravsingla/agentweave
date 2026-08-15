import asyncio, json, os
from dataclasses import asdict
from agentweave.proof import run_all_proofs

async def main():
    rows=await run_all_proofs('proof-results.json')
    payload=[asdict(x) for x in rows]; print(json.dumps(payload,indent=2,default=str))
    hard=[x for x in rows if not x.detail.get('skipped')]
    if os.getenv('AGENTWEAVE_REQUIRE_LIVE_PROOF')=='1' and not hard:
        print('No live marketplace/edge/PostgreSQL proof target was configured.')
        return 2
    return 0 if all(x.passed for x in hard) else 1

if __name__=='__main__': raise SystemExit(asyncio.run(main()))
