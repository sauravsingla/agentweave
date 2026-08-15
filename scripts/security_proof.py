import json, pathlib
from dataclasses import asdict
from agentweave.security_lab import SandboxValidationSuite, AdversarialValidationSuite

rows=[*AdversarialValidationSuite().run(),*SandboxValidationSuite().run()]
payload=[asdict(x) for x in rows]; pathlib.Path('security-report.json').write_text(json.dumps(payload,indent=2)); print(json.dumps(payload,indent=2))
raise SystemExit(0 if all(x.passed for x in rows) else 1)
