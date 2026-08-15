import argparse, json
from agentweave import AgentWeave, ScalabilityBenchmark

p=argparse.ArgumentParser(); p.add_argument('--sizes',default='10000,100000,1000000'); p.add_argument('--cap',type=int,default=None); args=p.parse_args()
w=AgentWeave(db_path=':memory:'); req=w.analyzer.analyze('analyze research and summarize')
rows=ScalabilityBenchmark().rank(w.matcher,req,tuple(int(x) for x in args.sizes.split(',')),max_runtime_agents=args.cap)
print(json.dumps(rows,indent=2))
