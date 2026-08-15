import asyncio, json, pathlib
from dataclasses import asdict
from agentweave.chaos import ChaosReliabilitySuite

async def main():
    rows=await ChaosReliabilitySuite().run()
    payload=[asdict(x) for x in rows]
    pathlib.Path('chaos-proof.json').write_text(json.dumps(payload,indent=2,default=str))
    print(json.dumps(payload,indent=2,default=str))
    return 0 if all(x.passed for x in rows) else 1

raise SystemExit(asyncio.run(main()))
