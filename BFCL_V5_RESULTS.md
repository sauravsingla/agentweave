# Frozen BFCL Routing-Pressure V5 Result

AgentWeave's **BFCL routing-pressure v5** study is frozen after its first successful scored run. The experiment uses untouched BFCL V4 `multiple` questions, deterministic BFCL-derived distractors to create 16-tool routing pressure, native BFCL evaluation, and the public `MadeAgents/Hammer2.1-1.5b` model running locally with no API key and $0 external API spend.

| Strategy | Native BFCL success | Original-candidate recall | Mean tools shown | Input tokens | Mean model latency |
|---|---:|---:|---:|---:|---:|
| Single-agent / all tools | 0/12 (0%) | 100.0% | 16.00 | 30,482 | 56.04 s |
| Random top-8 | 0/12 (0%) | 46.5% | 8.00 | 16,623 | 30.22 s |
| Semantic top-8 | 0/12 (0%) | 84.7% | 8.00 | 17,194 | 36.07 s |
| **AgentWeave** | **2/12 (16.67%)** | **77.1%** | **4.58** | **11,189** | **25.26 s** |

Against each matched baseline, AgentWeave's native-success difference is **+16.67 percentage points**. The paired bootstrap 95% interval is **[0.0, +41.67] pp** and exact McNemar **p = 0.5**. With only 12 tasks, this is a resource-constrained pilot and is **not statistically significant**.

Relative to the all-tools baseline, AgentWeave used **71.35% fewer model-visible tools**, **63.29% fewer input tokens**, and **54.92% lower mean model latency**, while being the only strategy to solve any task in this frozen sample.

The preregistered >=85% original-candidate-recall target was **not met**: AgentWeave reached **77.08%**. This negative hypothesis outcome is retained alongside the positive native-success and efficiency results.

## Freeze and provenance

- Study: `bfcl-routing-pressure-v5`
- Scored head: `e73374a2ca80f6d0ac4ed387ac50497915ebde9d`
- Workflow run: `31981730530`
- Evidence artifact: `9273004440`
- Artifact digest: `sha256:d10c78ccf1d8575d9b242fbb2dd4d0d358af2cda90c40c0e764cd08a0676b759`
- Pinned Gorilla/BFCL commit: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`
- Frozen machine-readable record: [`evaluation/bfcl-routing-pressure-v5-frozen.json`](evaluation/bfcl-routing-pressure-v5-frozen.json)

**Evidence boundary:** this is a BFCL-derived routing-pressure stress test, not an official full BFCL leaderboard score. It preserves untouched BFCL questions and native BFCL evaluation while deterministically augmenting model-visible tool context. Any future tuning or replication must use a new study id and a fresh untouched sample.
