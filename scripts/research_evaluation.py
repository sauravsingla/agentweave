import csv, json, pathlib
from dataclasses import asdict
from agentweave import AgentWeave, SyntheticAgentFactory
from agentweave.research import ResearchBenchmark

root=pathlib.Path(__file__).resolve().parents[1]
cases_path=root/'research'/'benchmark_cases.json'
cases=json.loads(cases_path.read_text())['cases']
weave=AgentWeave(db_path=':memory:',use_native=False)
for agent in SyntheticAgentFactory().build(1000,seed=19): weave.register(agent)
suite=ResearchBenchmark(seed=73); rows=suite.evaluate(weave,cases,max_agents=5)
aggregate=suite.aggregate(rows)
payload={
    'methodology_version':'1.0',
    'seed':73,
    'agent_population':1000,
    'case_count':len(cases),
    'aggregate':aggregate,
    'delta_vs_single_best':suite.bootstrap_delta(rows),
    'delta_quality_vs_single_best':suite.bootstrap_delta(rows,metric='quality_proxy'),
    'rows':[asdict(x) for x in rows],
}
pathlib.Path('research-evaluation.json').write_text(json.dumps(payload,indent=2))

with open('research-evaluation.csv','w',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=list(asdict(rows[0]).keys()))
    writer.writeheader(); writer.writerows(asdict(row) for row in rows)

methods=sorted(aggregate)
md=['# AgentWeave Research Evaluation','','Reproducible routing/team-selection benchmark. See `research/METHODOLOGY.md` for the protocol.','',
    '| Method | Coverage | Quality proxy | Trust | Latency ms | Cost | Team size | Redundancy | Diversity |',
    '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for method in methods:
    row=aggregate[method]
    md.append(f"| {method} | {row['coverage']:.4f} | {row['quality_proxy']:.4f} | {row['trust']:.4f} | {row['latency_ms']:.2f} | {row['cost']:.4f} | {row['team_size']:.2f} | {row['redundancy']:.4f} | {row['diversity']:.4f} |")
md += ['',f"Coverage delta vs single-best: **{payload['delta_vs_single_best']['mean_delta']:.4f}**, 95% bootstrap CI {payload['delta_vs_single_best']['ci95']}.",
       f"Quality-proxy delta vs single-best: **{payload['delta_quality_vs_single_best']['mean_delta']:.4f}**, 95% bootstrap CI {payload['delta_quality_vs_single_best']['ci95']}."]
pathlib.Path('research-evaluation.md').write_text('\n'.join(md)+'\n')

# Dependency-free SVG plot for paper/report artifacts.
width=900; bar_h=28; gap=12; left=220; max_width=600; height=80+len(methods)*(bar_h+gap)
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
     '<rect width="100%" height="100%" fill="white"/>',
     '<text x="20" y="30" font-family="sans-serif" font-size="20">AgentWeave benchmark: capability coverage</text>']
for i,method in enumerate(methods):
    y=55+i*(bar_h+gap); value=aggregate[method]['coverage']; w=max_width*value
    svg.append(f'<text x="20" y="{y+20}" font-family="sans-serif" font-size="13">{method}</text>')
    svg.append(f'<rect x="{left}" y="{y}" width="{w:.2f}" height="{bar_h}" fill="#4f6bed"/>')
    svg.append(f'<text x="{left+w+8:.2f}" y="{y+20}" font-family="sans-serif" font-size="13">{value:.3f}</text>')
svg.append('</svg>')
pathlib.Path('research-coverage.svg').write_text('\n'.join(svg))
print(json.dumps({'aggregate':aggregate,'delta_vs_single_best':payload['delta_vs_single_best']},indent=2))
