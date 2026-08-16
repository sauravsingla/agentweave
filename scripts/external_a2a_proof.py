import asyncio, json, os, pathlib
from dataclasses import asdict
from urllib.parse import urlparse
from agentweave.interoperability import A2AInteropSuite, InteropTarget


async def main():
    raw = os.getenv('AGENTWEAVE_EXTERNAL_A2A_TARGETS', '').strip()
    if not raw:
        raise SystemExit('AGENTWEAVE_EXTERNAL_A2A_TARGETS is required')

    items = json.loads(raw)
    if len(items) < 2:
        raise SystemExit('At least two independently hosted targets are required for external proof')

    targets = []
    for item in items:
        url = item['agent_card_url']
        host = (urlparse(url).hostname or '').lower()
        if host in {'localhost', '127.0.0.1', '::1'} or host.endswith('.local'):
            raise SystemExit(f'Local target is not an external proof: {url}')
        targets.append(InteropTarget(**item))

    retries = max(0, int(os.getenv('AGENTWEAVE_EXTERNAL_RETRIES', '1')))
    required = int(os.getenv('AGENTWEAVE_EXTERNAL_MIN_SUCCESSES', str(len(targets))))
    if required < 1 or required > len(targets):
        raise SystemExit('AGENTWEAVE_EXTERNAL_MIN_SUCCESSES must be between 1 and the target count')

    suite = A2AInteropSuite()
    prompt = 'AgentWeave independently hosted interoperability proof'
    results = list(await suite.run(targets, prompt))

    # Public external services can return transient 5xx / JSON-RPC internal errors.
    # Retry only the failed targets, preserving strict proof semantics for targets that
    # already succeeded and avoiding unnecessary duplicate calls.
    for _ in range(retries):
        failed = [i for i, result in enumerate(results) if not (result.discovered and result.invoked)]
        if not failed:
            break
        retried = await suite.run([targets[i] for i in failed], prompt)
        for index, result in zip(failed, retried):
            results[index] = result

    payload = [asdict(x) for x in results]
    pathlib.Path('external-a2a-proof.json').write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))

    successful = sum(1 for x in results if x.discovered and x.invoked)
    print(f'External A2A proof: {successful}/{len(results)} targets succeeded; required={required}')
    return 0 if successful >= required else 1


raise SystemExit(asyncio.run(main()))
