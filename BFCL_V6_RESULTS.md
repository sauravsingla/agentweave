# Frozen BFCL Routing-Pressure V6 Replication

This page records the first successful scored run of **BFCL routing-pressure v6**, a larger untouched replication of the frozen v5 pilot.

## Headline result

On **48 fresh BFCL V4 `multiple` tasks with zero overlap with v5**, AgentWeave was the only strategy to achieve any native BFCL successes:

| Strategy | Native BFCL success | Mean tools shown | Input tokens | Mean latency |
|---|---:|---:|---:|---:|
| Single-agent / all tools | 0/48 = **0.0%** | 16.00 | 124,821 | 55.92 s |
| Random top-8 | 0/48 = **0.0%** | 8.00 | 69,790 | 30.56 s |
| Semantic top-8 | 0/48 = **0.0%** | 8.00 | 70,271 | 35.87 s |
| **AgentWeave** | **6/48 = 12.5%** | **4.77** | **47,805** | **27.43 s** |

AgentWeave's paired native-success difference versus each matched baseline was **+12.5 percentage points**, with a **10,000-resample paired bootstrap 95% CI of +4.17 to +22.92 pp** and **exact McNemar p = 0.03125**.

Against the all-tools baseline, AgentWeave used approximately **70.18% fewer visible tools**, **61.70% fewer input tokens**, and **50.95% lower mean local-model latency**.

## Replication relationship to v5

The frozen v5 pilot used 12 tasks and produced AgentWeave **2/12 = 16.67%** versus **0/12** for all three matched baselines, but with McNemar **p = 0.5** because the sample was small.

V6 kept the v5 model, routing budgets, baselines, 16-tool pressure, generation settings, and native BFCL evaluation unchanged. It used a new content-blind sample and explicitly excluded all 12 frozen v5 task IDs. The resulting **6/48 = 12.5% vs 0/48** outcome therefore serves as a larger untouched replication of the directional v5 finding.

## Routing diagnostics

| Strategy | Mean original-candidate recall | All original candidates retained |
|---|---:|---:|
| Single-agent | 100.00% | 100.00% |
| Random top-8 | 48.44% | 10.42% |
| Semantic top-8 | **86.81%** | 66.67% |
| AgentWeave | 76.91% | 54.17% |

Semantic top-8 retained more original BFCL candidates than AgentWeave, yet still scored 0/48. AgentWeave achieved 6/48 while exposing fewer tools, so the native-success result cannot be explained by candidate retention alone.

## Reproducibility freeze

- Study: `bfcl-routing-pressure-v6`
- Scored head: `ca6ff084da4fe5c670421b99e7ad413650e60c33`
- Merged commit: `e8c5fd92a568002dfb1213ab5c0b2dd08f0e339b`
- BFCL/Gorilla commit: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`
- Workflow run: `31983991285`
- Artifact: `9275082744`
- Artifact digest: `sha256:db9bcca4e7f0d83b6b837b23a0ddf8a5bcd43b24a5d66554156ba794dca48c0e`
- Model: `MadeAgents/Hammer2.1-1.5b`
- External API spend: **$0**

The machine-readable frozen record is [`evaluation/bfcl-routing-pressure-v6-frozen.json`](evaluation/bfcl-routing-pressure-v6-frozen.json). The earlier frozen pilot is documented in [`BFCL_V5_RESULTS.md`](BFCL_V5_RESULTS.md).

## Evidence boundary

This is a **BFCL-derived routing-pressure replication**, not an official full BFCL leaderboard score. The experiment preserves untouched BFCL questions and native BFCL evaluation while deterministically augmenting the model-visible tool context. It is keyless, local, single-turn, and uses $0 external API spend.

The v6 result is frozen. Any tuning or further replication must use a new study ID and a fresh untouched sample.
