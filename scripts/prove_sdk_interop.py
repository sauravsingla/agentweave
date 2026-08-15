import argparse, asyncio, json, pathlib
from dataclasses import asdict
from agentweave.interoperability import A2AInteropSuite, InteropTarget

async def run(args):
    target=InteropTarget(args.name,args.card_url,args.implementation,args.transport)
    result=await A2AInteropSuite().run_target(target,args.prompt)
    payload=asdict(result)
    out=pathlib.Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2))
    print(json.dumps(payload,indent=2))
    return 0 if result.discovered and result.invoked else 1

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--name',required=True); p.add_argument('--implementation',required=True); p.add_argument('--card-url',required=True)
    p.add_argument('--transport',default='JSONRPC'); p.add_argument('--prompt',default='Say hello from AgentWeave interoperability CI.')
    p.add_argument('--output',required=True)
    raise SystemExit(asyncio.run(run(p.parse_args())))
