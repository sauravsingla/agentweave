import argparse, json, pathlib, platform, sys
from agentweave import AgentWeave, SyntheticAgentFactory
from agentweave.research import ScaleSuite

parser=argparse.ArgumentParser(); parser.add_argument('--sizes',default='10000,100000,1000000'); args=parser.parse_args()
weave=AgentWeave(db_path=':memory:')
rows=ScaleSuite(SyntheticAgentFactory()).run(weave,tuple(int(x) for x in args.sizes.split(',')))
payload={'environment':{'python':sys.version,'platform':platform.platform(),'native_available':weave.matcher.native_available},'results':rows}
pathlib.Path('scale-results.json').write_text(json.dumps(payload,indent=2))
md=['# AgentWeave Physical Scalability Benchmark','',f"Environment: `{payload['environment']['platform']}` / Python `{sys.version.split()[0]}`",'',
    '| Agents | Mode | Ranking s | Agents/s | Peak RSS MB | Team ops/s | Graph sample | Graph updates/s | Native speedup |',
    '|---:|---|---:|---:|---:|---:|---:|---:|---:|']
for row in rows:
    speedup=f"{row['native_speedup_vs_python']:.2f}x" if row.get('native_speedup_vs_python') else '—'
    md.append(f"| {row['agents']} | {row['mode']} | {row['ranking_seconds']:.4f} | {row['agents_per_second']:.1f} | {row['peak_rss_mb']:.1f} | {row['team_selection_ops_per_second']:.1f} | {row['graph_agents_sampled']} | {row['graph_updates_per_second']:.1f} | {speedup} |")
pathlib.Path('scale-results.md').write_text('\n'.join(md)+'\n')
print(json.dumps(payload,indent=2))
