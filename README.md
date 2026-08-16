# AgentWeave

**Knowledge-, capability-, trust-, policy-, and confidence-aware orchestration for heterogeneous AI agents.**

AgentWeave is an open-source framework for discovering, validating, selecting, and orchestrating AI agents across cloud, marketplaces, enterprise environments, and edge devices. It uses **A2A as the interoperability layer** and adds requirement intelligence, contextual trust, capability/knowledge graphs, placement and team optimization, governance, result verification, reputation learning, observability, sandboxing, **automatic runtime failover**, and **durable checkpoint recovery for multi-step workflows**.

[![CI](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml)
[![Deep Proof](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml)
[![A2A SDK Interop](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml)
[![Protocol Depth](https://github.com/sauravsingla/agentweave/actions/workflows/protocol-depth.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/protocol-depth.yml)
[![External Proof](https://github.com/sauravsingla/agentweave/actions/workflows/external-proof.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/external-proof.yml)
[![Team Advantage](https://github.com/sauravsingla/agentweave/actions/workflows/team-advantage.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/team-advantage.yml)
[![AgentBench](https://github.com/sauravsingla/agentweave/actions/workflows/agentbench-external.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/agentbench-external.yml)
[![ToolBench](https://github.com/sauravsingla/agentweave/actions/workflows/toolbench-external.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/toolbench-external.yml)
[![AgencyBench](https://github.com/sauravsingla/agentweave/actions/workflows/agencybench-external.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/agencybench-external.yml)
[![AgentProcessBench](https://github.com/sauravsingla/agentweave/actions/workflows/agentprocessbench-external.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/agentprocessbench-external.yml)
[![Untouched Generalization](https://github.com/sauravsingla/agentweave/actions/workflows/untouched-generalization.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/untouched-generalization.yml)
[![Router V7 Holdout](https://github.com/sauravsingla/agentweave/actions/workflows/router-v7-holdout.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/router-v7-holdout.yml)

> **A2A answers:** how can agents communicate?
>
> **AgentWeave adds:** which agents should communicate for this requirement, how confident are we in that requirement interpretation, can the agents be trusted, where should they execute, what should happen when a selected agent fails, how should work resume, and how should outputs be validated and learned from?

## Cross-benchmark evidence

AgentWeave is evaluated across four independent public benchmark distributions — **AgentBench, ToolBench, AgencyBench, and AgentProcessBench** — covering specialist selection, tool/API retrieval, capability-family routing, and post-hoc process-quality verification.

| Benchmark | Evaluation problem | Current AgentWeave result |
|---|---|---|
| **AgentBench** | Blind specialist selection | **52.0%** blind Hit@1; **89.9%** accuracy on committed routes at **46.3%** coverage |
| **ToolBench** | Tool/API retrieval over 4,856 APIs | **35.8% Hit@1**, **47.5% Hit@3**, **53.8% Hit@5**, MRR **0.440** |
| **AgencyBench** | Capability-family routing | **57.0%** zero-shot Hit@1; **67.2%** cumulative-context Hit@1; **92.2%** cumulative-context Hit@3 |
| **AgentProcessBench** | Label-blind trajectory process verification | **55.88%** step micro accuracy; **38.30%** first-error accuracy over **1,000 trajectories / 8,509 assistant steps** |

**Research takeaway:** AgentWeave's benchmark evidence now spans both **pre-execution selection** and **post-execution process verification** across four structurally different external datasets.

The AgentBench, ToolBench, and AgencyBench figures are **routing/selection metrics**. The AgentProcessBench figures are a **deterministic label-blind process-quality baseline** over published trajectories. None of these numbers is presented as a replacement for the original benchmarks' end-to-end task-success or official LLM-judge scores.

The next research step is to connect selection and process verification in one benchmark-native loop: **task → candidate discovery → capability/trust ranking → selected agent/tool/team → execution → process verification/native judge → outcome-driven reputation update**.

## Frozen-router generalization and external holdouts

To test whether routing improvements transfer beyond datasets already inspected during development, AgentWeave maintains a **frozen-router evaluation sequence**. Each router version is scored once on a newly preregistered external holdout; after the first successful scored run, that router/holdout pair is frozen. A later improvement must use a new router version and a new holdout rather than tuning against the prior test set.

| Evaluation | New untouched holdout | Tasks | Same-holdout comparison | Result |
|---|---|---:|---|---:|
| **Frozen original router** | General-AgentBench | **499** | Frozen router vs majority baseline | **15.6% Hit@1**, 20.8% macro; majority baseline 39.9% |
| **Router V2** | GSM8K + HumanEval + InterCode NL2Bash | **72** | Frozen router 52.8% → V2 | **54.2% Hit@1 (+1.4 pp)** |
| **Router V3** | MBPP + TruthfulQA + OSWorld | **72** | V2 31.9% → V3 | **76.4% Hit@1 (+44.4 pp)** |
| **Router V4** | CRUXEval + BrowserGym MiniWoB + WorkArena | **72** | V3 72.2% → V4 | **91.7% Hit@1 (+19.4 pp)** |
| **Router V5** | VisualWebArena | **72** | V4 38.9% → V5 | **77.8% interactive Hit@1 (+38.9 pp)** |
| **Router V6** | WebArena | **72** | V5 37.5% → V6 | **59.7% interactive Hit@1 (+22.2 pp)** |
| **Router V7** | AssistantBench | **72** | V6 73.6% → V7 | **91.7% search-family Hit@1 (+18.1 pp)** |

**Important comparison rule:** each row after the first uses a **different external holdout**. Therefore V2's 54.2%, V3's 76.4%, V4's 91.7%, V5's 77.8%, V6's 59.7%, and V7's 91.7% are **not a single cross-version leaderboard and must not be compared directly across rows**. The scientifically valid improvement is the within-row comparison between the previous router and the new router on the **same newly introduced holdout**.

The original General-AgentBench result is intentionally retained even though it is weak: the frozen router achieved **15.6% overall Hit@1**, showing poor broad-taxonomy transfer before the later research routers were developed. Router V2–V7 are kept under `research/` as separate experimental routers rather than silently changing that original result.

### Reproducibility and anti-tuning controls

- General-AgentBench development prompts remain pinned for the research-router development path.
- Each external holdout pins its source repository/dataset revision, task count, and deterministic sampling rule before scoring.
- Holdout family labels are attached only after predictions are produced where the protocol requires label-blind scoring.
- Every router version has a dedicated evaluation protocol under [`evaluation/`](evaluation/) and a GitHub Actions proof under [`.github/workflows/`](.github/workflows/).
- The frozen original proof is executed by [`untouched-generalization.yml`](.github/workflows/untouched-generalization.yml); subsequent proofs are executed by `router-v2-holdout.yml` through `router-v7-holdout.yml`.
- Poor or incomplete transfer results are preserved rather than overwritten; tuning against a scored holdout requires a new router version and a new test distribution.

### Generalization evidence boundary

These experiments measure **task-family / specialist routing transfer**, not native benchmark task completion. They do **not** claim GSM8K mathematical answer accuracy, HumanEval/MBPP code pass rates, OSWorld/WorkArena/WebArena browser-environment success, VisualWebArena visual grounding success, AssistantBench answer quality, production-user accuracy, provider latency, or billed model cost. The benchmark tasks are external and published; the reported metric is the router's ability to identify the intended capability family before the held-out label is used for scoring.

## Why AgentWeave?

Communication alone does not solve agent selection. Real agent ecosystems contain heterogeneous agents with different expertise, trust, costs, latency, execution locations, security boundaries, and implementation stacks.

AgentWeave is designed to:

- discover agents through A2A Agent Cards, registries, marketplaces, enterprise catalogs, and edge runtimes;
- infer structured requirements from raw task text with explicit confidence and ambiguity;
- validate capability, identity, security, policy, freshness, and historical evidence;
- match requirements to agents using capabilities, domains, knowledge, placement, trust, cost, and latency;
- form teams across coverage, trust, diversity, redundancy, cost, latency, and communication overhead;
- orchestrate A2A task lifecycle, streaming, cancellation, resume, subscription, and push notifications;
- detect runtime agent failure, record a negative trust/reputation outcome, re-rank remaining candidates, and automatically select a replacement;
- persist multi-step workflow checkpoints and resume after process restart without replaying completed steps;
- verify outputs using contradiction, citation/source-quality, uncertainty, NLI/verifier hooks, and consensus/conflict handling;
- learn from outcomes using persistent reputation and dynamic re-testing.

## Architecture

```text
Cloud / Marketplace / Enterprise / Edge Agents
                    │
              Agent Discovery
                    │
              Agent Registry
                    │
      Identity / Security / Benchmarks
                    │
        Requirement Intelligence
      lexical → semantic → optional LLM
                    │
     Capability + Knowledge Ontology
                    │
            Contextual Trust
                    │
        Matching + Placement
                    │
        Global Team Optimizer
                    │
                   A2A
                    │
      Runtime Failure Detection
                    │
       Trust Update + Re-ranking
                    │
      Replacement Agent / Team
                    │
      Durable Checkpoint / Resume
                    │
   Consensus + Conflict Resolution
                    │
     Result + Semantic Verification
                    │
      Reputation + Dynamic Retesting
```

## Runtime failover and durable workflow recovery

AgentWeave now supports a closed-loop recovery path when a selected agent fails during execution. The recovery manager records the failed outcome immediately, updates the failed agent's trust/reputation, excludes already-attempted agents, re-ranks the remaining candidates using the updated state, invokes the best compatible replacement, and can continue to another replacement if the first backup also fails.

The implemented runtime sequence is:

```text
requirement
   ↓
discover + rank candidates
   ↓
select Agent A
   ↓
Agent A fails
   ↓
detect failure
   ↓
negative trust/reputation update
   ↓
re-rank remaining candidates
   ↓
select Agent B
   ↓
retry / continue with prior successful context
   ↓
validate final outcome
   ↓
update reputation from the recovered result
```

| Failure/replacement behavior | Current support |
|---|---:|
| Chosen agent fails | ✅ |
| AgentWeave detects the runtime failure | ✅ |
| Failed-agent trust/reputation decreases automatically | ✅ |
| Remaining candidates are re-ranked after the trust update | ✅ |
| Replacement agent is selected automatically | ✅ |
| Multiple replacement attempts are supported | ✅ |
| Prior successful context is carried into recovery | ✅ |
| Final recovered outcome is validated | ✅ |
| Recovery events and effective agents are exposed in the result | ✅ |

The integration test [`tests/test_runtime_recovery.py`](tests/test_runtime_recovery.py) proves both **primary → backup → success** and **primary → first backup fails → second backup → success**, including automatic trust degradation and recovery-event ordering.

### Durable multi-step resume

For workflows that must survive more than an individual invocation failure, `DurableAgentWeave` adds persistent workflow checkpoints. Each completed step is persisted before the scheduler advances. If the process stops or a step cannot complete, a fresh AgentWeave process can load the same checkpoint and continue from `next_step_index` without replaying already-completed steps.

```text
Step 1 ✅  ┐
Step 2 ✅  │ persisted checkpoints
Step 3 ✅  ┘
Step 4 → Agent A fails ❌
                ↓
      failure + trust update persisted
                ↓
       process may restart
                ↓
       load workflow checkpoint
                ↓
       re-rank replacement agents
                ↓
       Agent B resumes Step 4
                ↓
Step 4 ✅
Step 5 ✅
```

The public API is intentionally separate from the single-task `AgentWeave.solve()` path:

```python
from agentweave import DurableAgentWeave, WorkflowStep

weave = DurableAgentWeave(db_path='agentweave.db')

steps = [
    WorkflowStep('collect', 'Collect evidence', {'research'}),
    WorkflowStep('analyze', 'Analyze the evidence', {'analysis'}),
    WorkflowStep('verify', 'Verify the conclusion', {'verification'}),
]

result = await weave.run_workflow(
    steps,
    workflow_id='case-42',
    max_failovers=2,
)

# A fresh process can later continue the same workflow.
result = await weave.resume_workflow('case-42', max_failovers=2)
```

Checkpoint persistence is available through the built-in SQLite store, PostgreSQL store, and replicated store path. The integration test [`tests/test_durable_workflow.py`](tests/test_durable_workflow.py) simulates a fresh process restart against the same durable database and verifies that completed steps are not replayed.

**Execution semantics:** completed steps are durable from AgentWeave's scheduler perspective. If the entire process dies while a remote agent is executing the current step but before the result is checkpointed, that in-flight step is **at-least-once**. AgentWeave sends a stable `workflow_id:step_id` idempotency key so a remote implementation can deduplicate repeated side effects and provide end-to-end exactly-once behavior when it supports idempotency.

**Evidence boundary:** the recovery behavior above is implemented and covered by automated failure-injection/integration tests. AgentWeave does not currently claim that the same failure/replacement sequence has been measured as a controlled outage inside an external production workload; that remains a useful next real-workload experiment.

## Requirement intelligence

`RequirementAnalyzer` now uses a layered inference path:

1. deterministic lexical and phrase signals;
2. generic semantic-intent inference for tasks whose implementation domain is implicit;
3. explicit `inference_confidence`, `inference_source`, and ambiguity metadata;
4. an optional pluggable semantic/LLM inferencer for low-confidence requests;
5. conservative reasoning fallback when specialist evidence is insufficient.

The built-in semantic layer is benchmark-label independent. AgentBench labels are never supplied to blind routing.

## A2A interoperability

AgentWeave supports Agent Card discovery, JSON-RPC and HTTP+JSON lifecycle operations, generated-stub gRPC lifecycle calls, streaming, task lookup/list/cancel, subscription, retry/resume, push-notification configuration, and an authenticated ASGI push receiver.

### Cross-SDK proof

Independent upstream A2A SDK agents were launched and invoked in GitHub Actions:

| SDK | Discovery | Invocation |
|---|---:|---:|
| Python | ✅ | ✅ |
| Go | ✅ | ✅ |
| JavaScript | ✅ | ✅ |
| Java | ✅ | ✅ |

### Independently hosted public proof

| Service | Discovery | Real invocation |
|---|---:|---:|
| Deep Research Archives | ✅ | ✅ |
| Delx Agent Operations Protocol | ✅ | ✅ |

Delx proof includes public registration bootstrap, runtime credential capture, and authenticated `message/send`.

### Official conformance

The Deep Proof workflow executes the official A2A TCK against AgentWeave as the system under test:

```bash
uv run ./run_tck.py --sut-host http://127.0.0.1:9998 --transport jsonrpc --level must
```

**Result: ✅ JSON-RPC MUST-level TCK.**

See [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md) for the tested compatibility boundary and SDK version policy. The Python TCK environment remains pinned to `a2a-sdk==1.1.0` for reproducibility; that pin is not presented as the only valid A2A implementation.

## External AgentBench evaluation

AgentWeave is evaluated on **490 published tasks** from the official `THUDM/AgentBench` repository, pinned to upstream commit `d1e4a10db08c87075c78972e48ecc182be03e2d5`:

| Environment | Tasks |
|---|---:|
| DBBench | 200 |
| KnowledgeGraph | 150 |
| OS Interaction | 140 |
| **Total** | **490** |

The latest blind evaluation was run on AgentWeave commit `a46cac91c7648e884cebb8a40dbf0ac218d08bd6`.

### Blind routing

The router receives **raw task text only**. AgentBench environment labels and expected specialist identities are withheld until after selection and are used only as scoring ground truth.

| Method | Blind specialist-selection rate |
|---|---:|
| **AgentWeave** | **52.0%** |
| Random | 19.2% |
| Capability-only | 1.0% |
| Single-best | 0.0% |
| Trust-only | 0.0% |

This remains materially above the earlier **34.1%** blind AgentWeave result after layered semantic requirement inference was introduced.

Per-domain blind accuracy:

| Domain | Accuracy |
|---|---:|
| Database | 31.5% |
| Knowledge graph | **58.7%** |
| Operating system | **74.3%** |

### Confidence-aware selective routing

AgentWeave can abstain rather than force a specialist when confidence is insufficient. With a specialist-domain confidence threshold of `0.65`:

| Metric | Result |
|---|---:|
| Coverage | **46.3%** — 227 / 490 tasks |
| Accuracy when committed | **89.9%** |
| Correct specialist across all tasks | **41.6%** |
| Abstained | 263 tasks |

Per-domain selective results:

| Domain | Coverage | Accuracy when committed |
|---|---:|---:|
| Database | 39.5% | 79.7% |
| Knowledge graph | 24.7% | **100.0%** |
| Operating system | 79.3% | **93.7%** |

The selective result is reported as an explicit accuracy-versus-coverage trade-off: **89.9% accuracy on committed routes at 46.3% coverage**, with abstentions counted separately rather than treated as correct routes.

### AgentBench interpretation boundary

- **External published data:** AgentBench task text and held-out environment/domain labels.
- **Synthetic data:** candidate specialist/generalist catalog, proficiencies, validation flags, trust values, latency, and cost.
- **Real measurement:** routing computation is executed and timed in GitHub Actions.
- **Not claimed:** original AgentBench end-to-end environment success, LLM answer quality, production-user accuracy, provider latency, or billed model cost.
- **No label leakage:** the environment label is used only after blind/selective routing for scoring.
- **Next research step:** execute selected agents inside end-to-end benchmark environments and score actual task outcomes, not only routing correctness.

Evidence is generated by `.github/workflows/agentbench-external.yml` and uploaded as JSON/Markdown workflow artifacts.

## External ToolBench evaluation

AgentWeave is also evaluated against **ToolBench** as an open-catalog capability/tool-routing problem. The workflow pins the official `OpenBMB/ToolBench` repository at `d56fdd89faf8c91fa135090b212bb9057ee5cfc2` and the external benchmark mirror used for the six evaluation splits at `36de9b189753ad5de276181974f97df15e8c3202`.

The executed GitHub Actions run evaluated **1,100 ToolBench queries** across **6 benchmark splits** against a global catalog containing **4,856 unique API records across 48 categories**. AgentWeave receives the raw query and global API metadata; each task's relevant-API association is hidden until after ranking and used only as scoring ground truth.

| Method | Hit@1 | Hit@3 | Hit@5 | MRR | Mean recall@5 | All relevant@5 |
|---|---:|---:|---:|---:|---:|---:|
| **AgentWeave** | **35.8%** | **47.5%** | **53.8%** | **0.440** | **34.7%** | **17.7%** |
| Random | 0.4% | 0.5% | 0.9% | 0.005 | 0.4% | 0.0% |

Mean AgentWeave ranking time across the 4,856-record catalog was **59.68 ms/task**, with **169.38 ms p95**.

Per-split results:

| ToolBench split | Tasks | Hit@1 | Hit@5 | MRR | Recall@5 |
|---|---:|---:|---:|---:|---:|
| G1 Instruction | 200 | 39.0% | 58.5% | 0.484 | 43.6% |
| G1 Category | 200 | 30.0% | 49.5% | 0.390 | 34.7% |
| G1 Tool | 200 | 36.5% | 54.0% | 0.445 | 40.0% |
| G2 Instruction | 200 | **41.0%** | **58.0%** | **0.489** | 34.0% |
| G2 Category | 200 | 34.5% | 52.5% | 0.423 | 29.3% |
| G3 Instruction | 100 | 32.0% | 47.0% | 0.383 | 18.8% |

### ToolBench interpretation boundary

- **External published data:** ToolBench task queries and API/tool metadata.
- **No relevance leakage:** the task-to-relevant-API relation is hidden during ranking and used only after ranking for scoring.
- **Controlled catalog priors:** candidate tools use equal synthetic trust, cost, and placement values so the benchmark isolates capability/tool retrieval rather than rewarding synthetic priors.
- **Real measurement:** ranking is physically executed and timed in GitHub Actions over the discovered API catalog.
- **Not claimed:** ToolEval end-to-end success, live RapidAPI/tool execution, final-answer quality, production provider latency, or billed API/model cost.
- **Next research step:** semantic embedding/reranking and end-to-end selected-tool execution, while keeping the ground-truth relevant APIs hidden during retrieval.

Evidence is generated by `.github/workflows/toolbench-external.yml` and uploaded as JSON/Markdown workflow artifacts.

## External AgencyBench evaluation

AgentWeave is also evaluated on **AgencyBench V2** as a blind capability-family routing problem. The workflow pins the official `GAIR-NLP/AgencyBench` repository at `ec65324be69e81bd4fe394ef6a86d48b8fa5da56`. The current evidence below was produced on AgentWeave commit `a46cac91c7648e884cebb8a40dbf0ac218d08bd6`.

AgencyBench's paper/README describes **138 tasks across 32 scenarios**. In the pinned V2 repository revision, the machine-readable `description.json` files yielded **128 string subtasks across 30 scenarios and 6 capability families**. AgentWeave reports the executed result on that parsed subset rather than claiming all 138 tasks.

Before zero-shot routing, the evaluator keeps only the task query/requirements and strips the `Deliverables` and `Rubric` sections. The parent AgencyBench capability-family label is hidden until after routing and used only as scoring ground truth.

### Zero-shot capability-family routing

| Method | Hit@1 | Top-2 team coverage | Hit@3 |
|---|---:|---:|---:|
| **AgentWeave** | **57.0%** | **75.0%** | **85.2%** |
| Single-best (Game) | 39.1% | — | — |
| Random | 21.9% | — | — |

Macro Hit@1 was **47.5%**. Mean routing time was **0.336 ms/task**, with **0.679 ms p95**.

Per-family zero-shot Hit@1:

| AgencyBench family | Parsed tasks | Hit@1 |
|---|---:|---:|
| Backend | 15 | 26.7% |
| Code | 29 | 58.6% |
| Frontend | 15 | 13.3% |
| Game | 50 | **80.0%** |
| Research | 9 | **66.7%** |
| MCP | 10 | 40.0% |

### Sequential / scenario-aware routing

AgencyBench scenarios contain multiple subtasks. A secondary routing analysis cumulatively provides the visible query text from earlier subtasks in the same scenario, while still withholding the family label, deliverables, rubric, outcomes, and native benchmark judge information.

| Metric | Result |
|---|---:|
| Independent task Hit@1 | 57.0% |
| **Cumulative-context Hit@1** | **67.2%** |
| **Cumulative-context Hit@3** | **92.2%** |
| First-subtask cold-start Hit@1 | 63.3% |
| Later-subtask independent Hit@1 | 55.1% |
| Scenario-majority family Hit@1 | **63.3%** |

This shows that visible prior task context can materially improve routing on multi-stage scenarios without exposing benchmark labels or outcomes.

### Scenario-held-out supervised routing

A deterministic scenario-stratified **60/40 development/test split** trains simple family text centroids only from development-scenario query text and evaluates on different held-out scenarios.

| Held-out metric | Result |
|---|---:|
| Hit@1 | **69.8%** |
| Hit@2 | **88.7%** |
| Hit@3 | **96.2%** |

The held-out test contains **53 tasks across 12 scenarios**; the development partition contains **75 tasks across 18 scenarios**.

### 5-fold scenario-grouped cross-validation

For a stronger supervised routing analysis, AgentWeave also runs **5-fold scenario-grouped stratified cross-validation**. A scenario is never split between train and test, and every task receives an out-of-fold prediction from family centroids trained only on other scenarios.

| Out-of-fold metric | Result |
|---|---:|
| **Hit@1** | **71.1%** |
| **Hit@2** | **90.6%** |
| **Hit@3** | **96.1%** |

Per-family out-of-fold Hit@1:

| AgencyBench family | Tasks | OOF Hit@1 |
|---|---:|---:|
| Backend | 15 | **66.7%** |
| Code | 29 | **62.1%** |
| Frontend | 15 | 33.3% |
| Game | 50 | **96.0%** |
| Research | 9 | **77.8%** |
| MCP | 10 | 30.0% |

The five held-out folds produced Hit@1 of **75.8%, 70.3%, 51.6%, 81.2%, and 100.0%** respectively. These figures are reported separately from the zero-shot result because the cross-validation router is supervised on other AgencyBench scenarios.

### AgencyBench interpretation boundary

- **External published data:** pinned AgencyBench V2 `description.json` task text.
- **Zero-shot blind routing:** capability-family labels are hidden until scoring and are not supplied to the router.
- **Reduced leakage:** deliverables and rubric text are removed before selection.
- **Fixed candidate metadata:** the six zero-shot capability-family descriptions are generic routing metadata and are not derived from benchmark examples.
- **Sequential analysis:** cumulative context uses only earlier visible task queries from the same scenario, not outcomes, labels, rubrics, or native judge information.
- **Held-out/cross-validation analyses:** training labels come only from development or other-fold scenarios; the held-out scenario label is used only for scoring.
- **Scenario grouping:** earlier and later subtasks from one scenario never cross the supervised train/test boundary.
- **Post-development caveat:** the held-out and cross-validation protocols were added after earlier aggregate inspection of this benchmark, so they are stronger than same-set tuning but are not presented as preregistered untouched evaluation.
- **Real measurement:** routing is physically executed and timed in GitHub Actions.
- **Not claimed:** AgencyBench end-to-end task score, long-horizon scenario completion, Docker visual/functional judge performance, user-simulation performance, or live model/tool execution.
- **Next research step:** execute selected agents inside the full AgencyBench scenarios and evaluate actual deliverables with the benchmark's native judges.

Evidence is generated by `.github/workflows/agencybench-external.yml` and uploaded as JSON/Markdown workflow artifacts, including separate scenario-grouped cross-validation evidence.

## External AgentProcessBench evaluation

AgentWeave is also evaluated on **RUCBM/AgentProcessBench** as a label-blind process-quality verification problem. The workflow pins the upstream repository at `0a42606b178a8c69d40c5765dc05c342f921e578` and evaluates all **1,000 published trajectories** across the benchmark's four datasets: HotpotQA, GAIA-dev, BFCL, and τ².

The verifier receives trajectory messages and tool traces but **does not receive the human `step_labels` while predicting**. Those labels are read only after prediction for scoring.

| Metric | Result |
|---|---:|
| Trajectories | **1,000** |
| Human-labeled assistant steps | **8,509** |
| **Step micro accuracy** | **55.88%** |
| **First-error accuracy** | **38.30%** |

Per-dataset results:

| Dataset | Records | Steps | Step micro acc. | First-error acc. | Trajectory exact acc. |
|---|---:|---:|---:|---:|---:|
| HotpotQA | 250 | 734 | **62.53%** | **59.20%** | **44.00%** |
| GAIA-dev | 250 | 1,628 | **34.95%** | **28.40%** | **16.80%** |
| BFCL | 250 | 2,590 | **66.76%** | **26.40%** | **10.80%** |
| τ² | 250 | 3,557 | **56.17%** | **39.20%** | **3.60%** |

### AgentProcessBench interpretation boundary

- **External published data:** 1,000 AgentProcessBench trajectories and their human step labels.
- **No label leakage during prediction:** trajectory/tool messages are used for prediction; `step_labels` are consulted only afterward for scoring.
- **Real measurement:** the deterministic verifier is executed over all 1,000 benchmark records in GitHub Actions.
- **What is measured:** agreement with human step-level `+1 / 0 / -1` labels and the location of the first `-1` error.
- **Not claimed:** end-to-end task completion, official AgentProcessBench LLM-judge performance, model reasoning quality, or production-agent reliability.
- **Why it matters to AgentWeave:** it adds post-execution process-quality evidence alongside the repository's pre-execution agent/tool/capability routing benchmarks.

Evidence is generated by `.github/workflows/agentprocessbench-external.yml` and uploaded as JSON/Markdown workflow artifacts.

## Scalability benchmark

A physical GitHub Actions run evaluated synthetic populations of 10K, 100K, and 1M agents.

| Agents | Mode | Ranking time | Throughput | Peak RSS |
|---:|---|---:|---:|---:|
| 10,000 | Python | 0.0417 s | 239,526 agents/s | 82.0 MB |
| 10,000 | Native C++ path | 0.2787 s | 35,881 agents/s | 100.2 MB |
| 100,000 | Python | 1.1234 s | 89,018 agents/s | 255.0 MB |
| 100,000 | Native C++ path | 3.0936 s | 32,324 agents/s | 255.0 MB |
| 1,000,000 | Python | 11.9981 s | 83,346 agents/s | 299.1 MB |
| 1,000,000 | Native C++ path | 34.1091 s | 29,318 agents/s | 299.1 MB |

The current native ranking path is slower than Python in this benchmark; AgentWeave reports that result directly. Graph-ingestion measurements for the 100K and 1M population runs use an explicitly bounded 50K graph sample rather than claiming a retained million-node graph.

## Synthetic research evaluation

The internal publication package remains a reproducible **synthetic routing/team-selection benchmark**, not a real-world task-accuracy claim.

| Method | Coverage | Trust | Latency | Cost | Quality proxy |
|---|---:|---:|---:|---:|---:|
| AgentWeave | 0.7604 | 0.7524 | 77.8 ms | 0.2222 | 0.6201 |
| Single-best | 0.7604 | 0.6822 | 298.3 ms | 0.5181 | 0.6324 |
| Random | 0.2354 | 0.5384 | 554.8 ms | 0.5037 | 0.1674 |
| Trust-only | 0.4833 | 0.8027 | 448.6 ms | 0.6440 | 0.4101 |
| Capability-greedy | 0.7604 | 0.6030 | 289.2 ms | 0.4974 | 0.6324 |
| Embedding-only | 0.7604 | 0.6822 | 319.5 ms | 0.5159 | 0.6324 |

`quality_proxy` is a routing metric, not factual correctness or human preference. AgentWeave currently improves latency/cost/trust against several baselines while the quality proxy remains slightly below single-best.

## Executable multi-agent team advantage benchmark

AgentWeave also includes a controlled **executable workload benchmark** designed to test whether optimized multi-agent team formation provides an advantage over simpler selection policies on the same tasks and agent catalog. Unlike the synthetic routing table above, the benchmark actually invokes handlers, measures wall-clock execution latency, accumulates invocation cost from execution profiles, injects runtime failures, and scores quality from the capabilities delivered by executed agents.

The benchmark compares four strategies across **12 multi-capability workloads**, including **4 induced primary-specialist failures**:

| Strategy | Task completion | Mean quality | Mean cost | Mean latency | P95 latency | Recovery success |
|---|---:|---:|---:|---:|---:|---:|
| **AgentWeave optimized team** | **100.0%** | **0.937** | **0.178** | **39.7 ms** | **73.8 ms** | **100.0%** |
| Single best agent | 0.0% | 0.720 | 0.420 | 115.4 ms | 115.4 ms | n/a |
| Random team | 0.0% | 0.160 | 0.200 | 40.7 ms | 72.6 ms | 0.0% |
| Capability-only team | 0.0% | 0.720 | 0.420 | 115.4 ms | 115.4 ms | n/a |

The AgentWeave strategy uses `AgentMatcher` plus `GlobalTeamOptimizer`; after a selected agent fails, trust is updated before the remaining candidates are re-ranked for replacement. The single-best baseline uses the top AgentWeave-ranked candidate, the random baseline uses deterministic seeded sampling, and the capability-only baseline greedily maximizes uncovered capabilities/proficiency while ignoring trust, cost, and latency. All strategies receive up to two replacement attempts so recovery is compared rather than withheld from the baselines.

The benchmark also produced a regression hardening change in `GlobalTeamOptimizer`: team candidates must contribute at least one required capability, preventing task-irrelevant agents from entering a team purely because trust, placement, or diversity terms make their overall objective positive.

Reproduce the benchmark locally with:

```bash
python scripts/team_advantage_benchmark.py
pytest -q tests/test_team_advantage_benchmark.py
```

CI runs the same proof in [`.github/workflows/team-advantage.yml`](.github/workflows/team-advantage.yml) and uploads `team-advantage-results.json` and `team-advantage-results.md` as workflow artifacts.

**Evidence boundary:** these are controlled executable-workload results with a synthetic agent catalog and deliberately injected failures. They demonstrate actual execution, measured latency/cost, failure handling, team selection, and recovery under the benchmark configuration, but they are **not** presented as an external production-user, billed-provider, or independent real-world workload benchmark.

## Security, identity, governance, storage, and reliability

The proof suite covers:

- malicious Agent Cards, prompt injection, data exfiltration, SSRF/link-local access, tool abuse, spoofing, Sybil/collusion, reputation poisoning, Byzantine disagreement, malformed results, and timeouts;
- Docker isolation with read-only filesystem, tmpfs, network, secret, CPU, memory, and PID controls;
- JWT Verifiable Credentials, revocation, certificate/key rotation, KMS/HSM integration boundaries, and workload-attestation boundaries;
- PostgreSQL concurrent writes, transaction/audit durability, reconnect recovery, and replica-aware behavior;
- governance for scopes, jurisdiction, residency, tools, locality, risk tiers, and human approval;
- chaos scenarios including disappearing/slow agents, network failure, malformed output, database failure, and process recovery.

A passing proof is evidence for the configured test runtime; it is not a formal security, HA, hardware-attestation, or compliance certification.

## What data is used?

| Category | Status | Current use |
|---|---|---|
| **Real systems / real execution** | ✅ | public A2A services, upstream SDK agents, official TCK, PostgreSQL, Docker/runtime controls, and executable team-advantage workload handlers |
| **External public benchmark data** | ✅ | AgentBench, ToolBench, AgencyBench, AgentProcessBench, General-AgentBench, GSM8K, HumanEval, InterCode NL2Bash, MBPP, TruthfulQA, OSWorld, CRUXEval, BrowserGym MiniWoB, WorkArena, VisualWebArena, WebArena, and AssistantBench holdouts |
| **Synthetic benchmark data** | ✅ | generated populations, capabilities, trust, latency/cost, adversarial fixtures, AgentBench candidate-agent catalog, controlled ToolBench priors, fixed AgencyBench zero-shot capability-family metadata, and the controlled team-advantage agent catalog/failure plan |
| **Supervised benchmark routing data** | ✅ | AgencyBench development/other-fold scenario labels used only to train the separately reported held-out and cross-validation routing analyses |
| **Production / real-world agent traces** | ❌ not claimed | no private production-user corpus, billed cost traces, or human-rated production outcomes |

The 10K/100K/1M execution is real computation over synthetic records. AgentBench, ToolBench, AgencyBench, AgentProcessBench, and the frozen-router V2–V7 holdouts provide external published benchmark data, while some candidate/catalog priors remain controlled synthetic or fixed metadata. The team-advantage benchmark performs real executable handler invocation over a controlled synthetic agent catalog with injected failures. Supervised AgencyBench results are separated from zero-shot routing so training labels are not conflated with blind-routing evidence; AgentProcessBench human step labels and frozen-router holdout family labels are withheld during prediction where specified and used only afterward for scoring.

## Getting started

### Install from source

```bash
python -m pip install -e '.[dev]'
pytest -q
```

Optional integrations:

```bash
python -m pip install -e '.[security,api,tck,grpc,native,postgres,aws,observability,edge,yaml,ontology]'
```

### Minimal example

```python
import asyncio
from agentweave import AgentWeave, AgentProfile, Capability, InMemoryA2AAdapter

async def main():
    bus = InMemoryA2AAdapter()
    weave = AgentWeave(a2a=bus, db_path=':memory:')

    agent = AgentProfile(
        'research-1',
        'Research Agent',
        [Capability('research', .9, True)],
    )
    weave.register(agent)
    bus.register_handler('research-1', lambda task: {'result': 'evidence-backed finding'})

    result = await weave.solve('Research and verify this topic', rounds=1, semantic_verify=True)
    print(result)

asyncio.run(main())
```

## CLI

```bash
agentweave version
agentweave doctor
agentweave graph-stats
agentweave plugins
agentweave --config agentweave.yaml config-check
agentweave solve --semantic-verify "Research and verify this topic"
```

## Release engineering

AgentWeave follows Semantic Versioning. `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CITATION.cff`, `docs/API_COMPATIBILITY.md`, and `docs/A2A_COMPATIBILITY.md` define maintenance and compatibility policy. The release workflow validates distributions and supports GitHub Release/PyPI trusted publishing when the corresponding release/tag and publishing configuration are present.

A packaged GitHub/PyPI release is a separate external release action; repository code and CI configuration alone are not presented as proof that a public package has already been published.

## External evidence boundaries

Some proof cannot be manufactured by repository code alone:

- real AWS Bedrock / Microsoft Foundry / Google Cloud marketplace execution requires credentials and configured/procured agents;
- physical Jetson / Raspberry Pi / NPU proof requires actual self-hosted hardware;
- live cloud KMS/HSM/TPM/TEE evidence requires corresponding external infrastructure;
- production adoption requires independent users, integrations, issues, pull requests, deployments, and citations.

## Contributing

Contributions, interoperability reports, marketplace adapters, benchmark scenarios, security tests, and real-world evaluation datasets are welcome. See `CONTRIBUTING.md`.

## License

Apache-2.0