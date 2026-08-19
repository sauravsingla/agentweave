# Reproduce / validate the AgentWeave BFCL-derived V6 result

This guide gives an outside researcher a **quick integrity check in well under 15 minutes** and a separate path for a **full model rerun**.

> **Evidence boundary:** this is a **BFCL-derived routing-pressure study**, not an official BFCL leaderboard score. The BFCL questions and native BFCL evaluator are preserved, while the model-visible tool context is deterministically augmented.

## 1. Quick validation — about 2–5 minutes

Requirements: Git and Python 3.10+.

```bash
git clone https://github.com/sauravsingla/agentweave.git
cd agentweave
python - <<'PY'
import json
from pathlib import Path

p = Path('evaluation/bfcl-routing-pressure-v6-frozen.json')
d = json.loads(p.read_text())

assert d['study_id'] == 'bfcl-routing-pressure-v6'
assert d['status'] == 'frozen-after-first-successful-score'
assert d['benchmark_commit'] == '6ea57973c7a6097fd7c5915698c54c17c5b1b6c8'
assert d['model'] == 'MadeAgents/Hammer2.1-1.5b'
assert d['sample_size'] == 48
assert d['v5_overlap'] == 0

r = d['results']
assert r['agentweave']['successes'] == 6
assert r['agentweave']['n'] == 48
assert r['single-agent']['successes'] == 0
assert r['random-router']['successes'] == 0
assert r['semantic-router']['successes'] == 0

for name in (
    'agentweave_vs_single_agent',
    'agentweave_vs_random_router',
    'agentweave_vs_semantic_router',
):
    c = d['comparisons'][name]
    assert c['difference_pp'] == 12.5
    assert c['exact_mcnemar_p'] == 0.03125

print('PASS: frozen BFCL-derived V6 record is internally consistent')
print('AgentWeave:', r['agentweave']['successes'], '/', r['agentweave']['n'])
print('Baselines: 0/48, 0/48, 0/48')
print('McNemar p:', d['comparisons']['agentweave_vs_single_agent']['exact_mcnemar_p'])
print('Pinned BFCL commit:', d['benchmark_commit'])
print('Canonical workflow run:', d['workflow_run_id'])
print('Artifact digest:', d['artifact_digest'])
PY
```

Expected headline output:

```text
PASS: frozen BFCL-derived V6 record is internally consistent
AgentWeave: 6 / 48
Baselines: 0/48, 0/48, 0/48
McNemar p: 0.03125
```

Then inspect the human-readable result record:

- [`BFCL_V6_RESULTS.md`](../BFCL_V6_RESULTS.md)
- [`evaluation/bfcl-routing-pressure-v6-frozen.json`](../evaluation/bfcl-routing-pressure-v6-frozen.json)

The frozen record also identifies the canonical scored head, pinned Gorilla/BFCL commit, workflow run, artifact ID, and artifact digest.

## 2. Validate the protocol against the pinned BFCL source

This checks the deterministic sample/protocol without downloading or running the 1.5B model.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -U pip
pip install -e '.[dev]'
pip install 'bfcl-eval==2025.12.17' 'transformers>=4.47,<6' 'sentence-transformers>=5.1,<6' torch soundfile

git clone --filter=blob:none https://github.com/ShishirPatil/gorilla.git external-gorilla
cd external-gorilla
git checkout 6ea57973c7a6097fd7c5915698c54c17c5b1b6c8
cd ..

pytest -q tests/test_bfcl_native_live_study.py

python scripts/bfcl_native_live_study.py \
  --bfcl-root external-gorilla/berkeley-function-call-leaderboard \
  --output bfcl-native-live-results \
  --validate-only
```

Dependency installation time varies by machine, so this second path may exceed 15 minutes on a cold environment. The first path intentionally requires only Git and Python.

## 3. Full native rerun

To independently rerun the local model and native BFCL evaluation, use the same command without `--validate-only`:

```bash
python scripts/bfcl_native_live_study.py \
  --bfcl-root external-gorilla/berkeley-function-call-leaderboard \
  --output bfcl-native-live-results
```

This downloads/runs `MadeAgents/Hammer2.1-1.5b` and can take substantially longer than 15 minutes depending on hardware. It is **not** presented as a 15-minute reproduction.

The repository workflow implementing the same frozen path is [`.github/workflows/bfcl-native-live.yml`](../.github/workflows/bfcl-native-live.yml).

## Canonical V6 facts

| Item | Frozen value |
|---|---|
| Study | `bfcl-routing-pressure-v6` |
| Tasks | 48 fresh BFCL V4 `multiple` tasks |
| V5 overlap | 0 |
| Model | `MadeAgents/Hammer2.1-1.5b` |
| BFCL/Gorilla commit | `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8` |
| AgentWeave | **6/48 = 12.5%** |
| All tools | 0/48 |
| Random top-8 | 0/48 |
| Semantic top-8 | 0/48 |
| Exact McNemar vs each baseline | **p = 0.03125** |
| Paired bootstrap 95% CI | **+4.17 to +22.92 pp** |
| External API spend | **$0** |

## What counts as an independent reproduction?

A useful external reproduction should report:

1. the AgentWeave commit used;
2. the pinned BFCL/Gorilla commit;
3. hardware and software environment;
4. whether the run was validation-only or a full model rerun;
5. generated result artifacts; and
6. any difference from the frozen outcome.

Please do **not** overwrite or reinterpret the frozen V6 record. A scientifically new experiment should use a new study ID and a fresh untouched sample.
