import asyncio, json, os, pathlib
from dataclasses import asdict
from urllib.parse import urlparse
from agentweave.interoperability import A2AInteropSuite, InteropTarget

async def main():
    raw=os.getenv('AGENTWEAVE_EXTERNAL_A2A_TARGETS','').strip()
    if not raw:
        raise SystemExit('AGENTWEAVE_EXTERNAL_A2A_TARGETS is required')
    items=json.loads(raw)
    if len(items)<2:
        raise SystemExit('At least two independently hosted targets are required for external proof')
    targets=[]
    for item in items:
        url=item['agent_card_url']; host=(urlparse(url).hostname or '').lower()
        if host in {'localhost','127.0.0.1','::1'} or host.endswith('.local'):
            raise SystemExit(f'Local target is not an external proof: {url}')
        targets.append(InteropTarget(**item))
    results=await A2AInteropSuite().run(targets,'AgentWeave independently hosted interoperability proof')
    payload=[asdict(x) for x in results]
    pathlib.Path('external-a2a-proof.json').write_text(json.dumps(payload,indent=2))
    print(json.dumps(payload,indent=2))
    return 0 if all(x.discovered and x.invoked for x in results) else 1

raise SystemExit(asyncio.run(main()))
