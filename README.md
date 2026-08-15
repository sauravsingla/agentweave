# AgentWeave

**Knowledge-, capability-, trust-, policy-, and confidence-aware orchestration for heterogeneous AI agents.**

AgentWeave is an open-source framework for discovering, validating, selecting, and orchestrating AI agents across cloud, marketplaces, enterprise environments, and edge devices. It uses **A2A as the interoperability layer** and adds requirement intelligence, contextual trust, capability/knowledge graphs, placement and team optimization, governance, result verification, reputation learning, observability, and sandboxing.

[![CI](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml)
[![Deep Proof](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/deep-proof.yml)
[![A2A SDK Interop](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/sdk-interop.yml)
[![Protocol Depth](https://github.com/sauravsingla/agentweave/actions/workflows/protocol-depth.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/protocol-depth.yml)
[![External Proof](https://github.com/sauravsingla/agentweave/actions/workflows/external-proof.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/external-proof.yml)
[![AgentBench](https://github.com/sauravsingla/agentweave/actions/workflows/agentbench-external.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/agentbench-external.yml)
[![ToolBench](https://github.com/sauravsingla/agentweave/actions/workflows/toolbench-external.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/toolbench-external.yml)
[![AgencyBench](https://github.com/sauravsingla/agentweave/actions/workflows/agencybench-external.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/agencybench-external.yml)

> **A2A answers:** how can agents communicate?
>
> **AgentWeave adds:** which agents should communicate for this requirement, how confident are we in that requirement interpretation, can the agents be trusted, where should they execute, and how should their outputs be validated and learned from?

## Cross-benchmark routing evidence

AgentWeave is evaluated across three independent public benchmark distributions — **AgentBench, ToolBench, and AgencyBench** — to test whether the same routing framework generalizes across specialist selection, tool/API retrieval, and capability-family routing rather than being tuned to a single benchmark shape.

| Benchmark | Routing problem | Current AgentWeave result |
|---|---|---|
| **AgentBench** | Blind specialist selection | **52.0%** blind Hit@1; **89.9%** accuracy on committed routes at **46.3%** coverage |
| **ToolBench** | Tool/API retrieval over 4,856 APIs | **35.8% Hit@1**, **47.5% Hit@3**, **53.8% Hit@5**, MRR **0.440** |
| **AgencyBench** | Capability-family routing | **57.0%** zero-shot Hit@1; **67.2%** cumulative-context Hit@1; **92.2%** cumulative-context Hit@3 |

**Research takeaway:** the same capability-, knowledge-, confidence-, and evidence-aware routing architecture generalizes across agent selection, tool retrieval, and multi-stage capability routing on three structurally different external benchmarks.

These are **routing/selection metrics**, not direct replacements for the end-to-end task-success metrics reported in the original AgentBench, ToolBench, and AgencyBench papers. The current evidence supports the narrower claim that AgentWeave can reduce heterogeneous candidate spaces to relevant specialists before execution; it does **not** claim that its routing percentages directly outperform the papers' end-to-end agent scores.

The next research step is to connect this selection evidence to benchmark-native execution: **task → candidate discovery → capability/trust ranking → selected agent/tool/team → execution → native judge → outcome-driven reputation update**.

## Why AgentWeave?

Communication alone does not solve agent selection. Real agent ecosystems contain heterogeneous agents with different expertise, trust, costs, latency, execution locations, security boundaries, and implementation stacks.

AgentWeave is designed to:

- discover agents through A2A Agent Cards, registries, marketplaces, enterprise catalogs, and edge runtimes;
- infer structured requirements from raw task text with explicit confidence and ambiguity;
- validate capability, identity, security, policy, freshness, and historical evidence;
- match requirements to agents using capabilities, domains, knowledge, placement, trust, cost, and latency;
- form teams across coverage, trust, diversity, redundancy, cost, latency, and communication overhead;
- orchestrate A2A task lifecycle, streaming, cancellation, resume, subscription, and push notifications;
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
 Streaming / Long-running / Push Tasks
                    │
   Consensus + Conflict Resolution
                    │
     Result + Semantic Verification
                    │
      Reputation + Dynamic Retesting
```

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
| **Real systems / real execution** | ✅ | public A2A services, upstream SDK agents, official TCK, PostgreSQL, Docker/runtime controls |
| **External public benchmark data** | ✅ | 490 AgentBench tasks, 1,100 ToolBench queries with 4,856 API records, and 128 parsed AgencyBench V2 subtasks |
| **Synthetic benchmark data** | ✅ | generated populations, capabilities, trust, latency/cost, adversarial fixtures, AgentBench candidate-agent catalog, controlled ToolBench priors, and fixed AgencyBench zero-shot capability-family metadata |
| **Supervised benchmark routing data** | ✅ | AgencyBench development/other-fold scenario labels used only to train the separately reported held-out and cross-validation routing analyses |
| **Production / real-world agent traces** | ❌ not claimed | no private production-user corpus, billed cost traces, or human-rated production outcomes |

The 10K/100K/1M execution is real computation over synthetic records. AgentBench, ToolBench, and AgencyBench provide external published benchmark task data, while some candidate/catalog priors remain controlled synthetic or fixed metadata. Supervised AgencyBench results are separated from zero-shot routing so training labels are not conflated with blind-routing evidence.

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