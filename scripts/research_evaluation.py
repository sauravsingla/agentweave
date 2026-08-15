import json, pathlib
from dataclasses import asdict
from agentweave import AgentWeave, SyntheticAgentFactory
from agentweave.research import ResearchBenchmark

w=AgentWeave(db_path=':memory:',use_native=False)
for a in SyntheticAgentFactory().build(250,seed=19): w.register(a)
cases=[
    'research and summarize evidence',
    'analyze and verify a technical claim',
    'plan and optimize an engineering workflow',
    'retrieve research then analyze and summarize',
    'code analyze and verify a solution',
    'research plan analyze and summarize a complex requirement',
]*10
suite=ResearchBenchmark(seed=73); rows=suite.evaluate(w,cases,max_agents=5)
payload={'aggregate':suite.aggregate(rows),'delta_vs_single_best':suite.bootstrap_delta(rows),'rows':[asdict(x) for x in rows]}
pathlib.Path('research-evaluation.json').write_text(json.dumps(payload,indent=2))
print(json.dumps(payload['aggregate'],indent=2)); print(json.dumps(payload['delta_vs_single_best'],indent=2))
