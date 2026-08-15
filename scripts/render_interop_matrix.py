import json, pathlib, sys
root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'interop-results')
rows=[]
for path in sorted(root.glob('*.json')):
    d=json.loads(path.read_text())
    rows.append(d)
print('# AgentWeave A2A SDK Compatibility Matrix')
print()
print('| SDK implementation | Agent Card discovery | SendMessage invocation | Transport | Streaming advertised | Result |')
print('|---|---:|---:|---|---:|---|')
for d in rows:
    ok=bool(d.get('discovered')) and bool(d.get('invoked'))
    print(f"| {d.get('implementation','unknown')} | {'✅' if d.get('discovered') else '❌'} | {'✅' if d.get('invoked') else '❌'} | {d.get('transport') or 'unknown'} | {'✅' if d.get('streaming_advertised') else '—'} | {'PASS' if ok else 'FAIL'} |")
print()
passed=sum(1 for d in rows if d.get('discovered') and d.get('invoked'))
print(f'**Summary:** {passed}/{len(rows)} independent SDK implementations passed AgentWeave discovery and live invocation.')
if not rows or passed != len(rows):
    raise SystemExit(1)
