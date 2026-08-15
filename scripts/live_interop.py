import asyncio, json, os, sys
from agentweave import A2AInteropSuite

async def main():
    targets=A2AInteropSuite.from_env()
    if not targets:
        print('AGENTWEAVE_A2A_TARGETS is empty; provide JSON array of {name,agent_card_url,implementation}.',file=sys.stderr); return 2
    suite=A2AInteropSuite(); results=await suite.run(targets)
    payload=[r.__dict__ for r in results]; print(json.dumps(payload,indent=2))
    return 0 if all(r.invoked for r in results) else 1

if __name__=='__main__': raise SystemExit(asyncio.run(main()))
