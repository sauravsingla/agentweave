import argparse, json, pathlib
from agentweave import AgentWeave, SyntheticAgentFactory
from agentweave.research import ScaleSuite

p=argparse.ArgumentParser(); p.add_argument('--sizes',default='10000,100000,1000000'); args=p.parse_args()
w=AgentWeave(db_path=':memory:'); rows=ScaleSuite(SyntheticAgentFactory()).run(w,tuple(int(x) for x in args.sizes.split(',')))
pathlib.Path('scale-results.json').write_text(json.dumps(rows,indent=2)); print(json.dumps(rows,indent=2))
