# BFCL routing-pressure v6 — frozen replication

AgentWeave v6 is a **48-task untouched replication** of the frozen v5 BFCL-derived routing-pressure pilot. It uses the same pinned BFCL source, local model, 16-tool pressure, baselines, AgentWeave 4-provider/6-tool budget, generation settings, and native BFCL evaluator. Every v5 task is excluded from v6.

| Strategy | Native BFCL success | Original-candidate recall | Mean tools shown | Input tokens | Mean latency |
|---|---:|---:|---:|---:|---:|
| Single-agent | **0/48 (0%)** | 100.0% | 16.00 | 124,821 | 55.92 s |
| Random top-8 | **0/48 (0%)** | 48.44% | 8.00 | 69,790 | 30.56 s |
| Semantic top-8 | **0/48 (0%)** | 86.81% | 8.00 | 70,271 | 35.87 s |
| **AgentWeave** | **6/48 (12.5%)** | 76.91% | **4.77** | **47,805** | **27.43 s** |

Compared with every matched baseline, AgentWeave's native-success difference was **+12.5 percentage points**. Exact paired McNemar **p = 0.03125**; the paired 10,000-resample bootstrap 95% interval was **+4.17 to +22.92 pp**.

Compared with the all-tools single-agent baseline, AgentWeave used **70.18% fewer visible tools**, **61.70% fewer input tokens**, and **50.95% lower mean model latency**.

## V5 → V6 replication

The frozen v5 pilot used 12 tasks and found AgentWeave at **2/12 (16.67%)** while all three matched baselines were **0/12**; that pilot was directionally positive but not statistically significant (McNemar p = 0.5). V6 repeated the same configuration on **48 fresh tasks with zero v5 overlap** and found AgentWeave at **6/48 (12.5%)** while all three baselines again remained **0/48**, with paired McNemar p = 0.03125.

This strengthens the evidence that routing-pressure reduction can improve native tool-call validity for this fixed local model while materially reducing tool context, token load, and latency.

## Scientific boundary

This is a **BFCL-derived routing-pressure replication**, not an official full BFCL leaderboard score. The BFCL questions and native BFCL evaluator are retained, but model-visible tool context is deterministically augmented with same-category distractors. The run is keyless, local, single-turn, and has **$0 external API spend**.

Frozen machine-readable evidence: [`evaluation/bfcl-routing-pressure-v6-frozen.json`](evaluation/bfcl-routing-pressure-v6-frozen.json).

Workflow run: `31983991285`  
Artifact: `9275082744`  
Artifact digest: `sha256:db9bcca4e7f0d83b6b837b23a0ddf8a5bcd43b24a5d66554156ba794dca48c0e`
