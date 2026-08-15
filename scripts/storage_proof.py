import json, os, pathlib
from dataclasses import asdict
from agentweave.storage_proof import PostgresDurabilityProof

dsn=os.environ['AGENTWEAVE_POSTGRES_DSN']
rows=PostgresDurabilityProof(dsn).run()
payload=[asdict(x) for x in rows]
pathlib.Path('storage-proof.json').write_text(json.dumps(payload,indent=2,default=str))
print(json.dumps(payload,indent=2,default=str))
raise SystemExit(0 if all(x.passed for x in rows) else 1)
