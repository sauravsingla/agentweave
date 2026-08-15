import asyncio, json, pathlib
from dataclasses import asdict
from agentweave.security_lab import SandboxValidationSuite, RedTeamValidationSuite

async def main():
    suite=RedTeamValidationSuite()
    rows=[*suite.run(),*(await suite.run_async()),*SandboxValidationSuite().run()]
    payload=[asdict(x) for x in rows]
    pathlib.Path('security-report.json').write_text(json.dumps(payload,indent=2,default=str))
    print(json.dumps(payload,indent=2,default=str))
    return 0 if all(x.passed for x in rows) else 1

raise SystemExit(asyncio.run(main()))
