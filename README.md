# AgentWeave — Route Before You Reason

[![CI](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agentweave-router.svg)](https://pypi.org/project/agentweave-router/)
[![Python](https://img.shields.io/pypi/pyversions/agentweave-router.svg)](https://pypi.org/project/agentweave-router/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22913460.svg)](https://doi.org/10.5281/zenodo.22913460)

**Pre-inference routing and secure execution for tool-rich LLM and multi-agent systems.**

**PyPI:** `agentweave-router` · **Python import:** `agentweave` · **Current release:** `v0.7.1`

AgentWeave reduces the tools or agents visible to a model before inference while keeping **scope policy, authorization, provenance, recovery, and execution explicit**.

> **Your agent has 100+ tools. Don't make the model reason over all of them. Route first, then reason over a smaller relevant action space.**

**70.18% fewer tools exposed · 61.70% fewer input tokens · 50.95% lower mean local-model latency**  
**MCP · A2A · LangGraph · AutoGen · policy-aware routing · recovery · reproducible evaluation**

**Quick links:** [30-second start](#30-second-start) · [Canonical runtime](#canonical-runtime) · [Results](#results-at-a-glance) · [0.7 quickstart](docs/QUICKSTART_0_7.md) · [MCP](docs/MCP_INTEGRATION.md) · [Contribute](CONTRIBUTING.md) · [Discussions](https://github.com/sauravsingla/agentweave/discussions) · [Road to 1.0](docs/ROAD_TO_1_0.md) · [Paper](https://arxiv.org/abs/2608.23078) · [Zenodo v0.7.0](https://zenodo.org/records/22913460)

```text
catalog
  ↓
deterministic scope / permissions
  ↓
pre-inference routing
  ↓
small model-visible action space
  ↓
model tool selection
  ↓
schema validation
  ↓
argument-aware authorization
  ↓
execution
  ↓
bounded recovery / rediscovery
```

AgentWeave does **not** replace MCP, LangGraph, AutoGen, A2A, or your model. It provides a provider-neutral routing and execution boundary around them.

## 30-second start

Install the base package from PyPI:

```bash
pip install agentweave-router
```

The PyPI distribution is `agentweave-router`; Python imports use `agentweave` (and the bundled `agentweave_byom` adapter package). For the MCP example below, install the MCP extra:

```bash
pip install 'agentweave-router[mcp]'
```

```python
from agentweave import AgentWeaveApplication
from agentweave_byom import OpenAICompatibleModelAdapter

model = OpenAICompatibleModelAdapter(
    model="my-model",
    base_url="https://model.example/v1",
    api_key="...",
)

app = AgentWeaveApplication.from_mcp(
    "https://tools.example/mcp",
    model=model,
    max_tools=8,
)

result = await app.run("Find invoice INV-7")
```

`AgentWeaveApplication` owns the MCP/runtime/plugin lifecycle. AgentWeave handles discovery, scope policy, routing, schema validation, argument-aware authorization, execution, bounded recovery, provenance, and telemetry.

Several MCP servers can be composed without silently collapsing same-name tools:

```python
app = AgentWeaveApplication.from_mcps(
    {
        "billing": "https://billing.example/mcp",
        "crm": "https://crm.example/mcp",
    },
    model=model,
)
```

If both servers expose native `search`, the model sees collision-safe names such as `billing__search` and `crm__search`, while execution is dispatched by canonical tool identity and the MCP servers still receive the native tool name.

Try the self-contained [multi-MCP collision example](examples/multi_mcp_collision.py):

```bash
python -m pip install -e '.[mcp]'
python examples/multi_mcp_collision.py
```

It starts two in-process MCP servers and uses a scripted model to select both aliases, prints each alias and canonical identity, and verifies one native `search` call reached each provider. No credentials, external model or network service are required.


For a provider-neutral local example without MCP, run [`examples/local_runtime.py`](examples/local_runtime.py):

```bash
python -m pip install -e '.[dev]'
python examples/local_runtime.py
```

It routes an addition request from three local tools to `add_numbers`, prints the routed and
model-visible tools, and executes the selected function through `CallableExecutor`, returning 42.
The model adapter is deliberately scripted for this fixed request; no API keys, external services,
network access, or optional integration packages are needed to run it after installation. Routing,
schema validation, authorization, and execution use the real `AgentWeaveRuntime` pipeline.
See [`docs/QUICKSTART_0_7.md`](docs/QUICKSTART_0_7.md) for connecting a model provider.

For repository development:

```bash
git clone https://github.com/sauravsingla/agentweave.git
cd agentweave
python -m pip install -e '.[dev]'
pytest -q
```

## Canonical runtime

`AgentWeaveRuntime` is the primary 0.7+ execution surface. It enforces one ordering instead of asking every integration to wire security correctly:

```text
catalog → scope → route → model → validate arguments → authorize → execute → recover
```

Key normalized contracts are `ToolSpec`, `ToolCall`, `ToolResult`, `ModelResponse`, `RunContext`, and `RuntimeResult`.

Tool identity is separate from the function name shown to the model. This matters when several providers expose names such as `search`, `read`, or `query`: stable provider/source IDs are preserved and duplicate model-visible names must be explicitly aliased rather than silently collapsed.

Model-generated arguments are validated against each `ToolSpec.input_schema` before authorization or execution. Authorization policies receive the resolved tool identity, arguments, provider/source metadata, tenant/security context, and model-visible set. Calls outside the routed set fail closed.

Every run also returns per-stage telemetry for catalog discovery, scope/routing, model calls, schema validation, authorization, execution, and recovery.

### MCP runtime

```bash
pip install 'agentweave-router[mcp]'
```

The simplest lifecycle-safe path is the application factory:

```python
from agentweave import AgentWeaveApplication
from agentweave_byom import OpenAICompatibleModelAdapter

model = OpenAICompatibleModelAdapter(
    model="my-model",
    base_url="https://model.example/v1",
)

app = AgentWeaveApplication.from_mcp(
    "https://tools.example/mcp",
    model=model,
)

result = await app.run("Search the codebase for the routing implementation")
```

For advanced control, `MCPConnection`, `MCPToolCatalog`, and `MCPExecutor` remain public integration components. The catalog and executor can share one lifecycle-owned MCP session. HTTP MCP targets are revalidated before connection establishment; AgentWeave-owned HTTP traffic uses `SafeHttpTransport` for endpoint validation, DNS pinning/rebinding checks, guarded redirects, Host/SNI preservation, and cross-origin credential stripping. The MCP SDK still owns its protocol wire transport unless an application supplies a custom client factory.

### Application and plugins

`AgentWeaveApplication` owns runtime and plugin startup/shutdown as one async boundary. Plugin startup is version-checked and transactional, so a partial startup failure is rolled back.

```python
from agentweave import AgentWeaveApplication

app = AgentWeaveApplication.from_file("agentweave.yaml")
result = await app.run("Find the invoice and verify it")
```

## When should I use AgentWeave?

Use AgentWeave when a model or agent can access a **large heterogeneous catalog of tools or specialist agents** and the model-visible action space should be reduced before inference.

Typical use cases include MCP servers with large tool catalogs, multi-agent specialist pools, enterprise capability catalogs, A2A ecosystems, LangGraph workflows, AutoGen teams, marketplaces, cloud agents, and edge runtimes.

If deterministic role, tenant, permission, or policy scope already reduces the catalog sufficiently, apply that first. AgentWeave's task-aware routing operates only on the permitted remainder.

## Integration model

| Stack | AgentWeave boundary |
|---|---|
| **MCP** | `AgentWeaveApplication.from_mcp()` / `.from_mcps()` or lower-level `MCPToolCatalog` + `MCPExecutor` + shared `MCPConnection` |
| **LangGraph** | `AgentWeaveLangGraphNode` / `langgraph_node()` backed by `runtime.preview_route()` |
| **AutoGen** | `AgentWeaveAutoGenSelector` backed by the public runtime API |
| **A2A** | discovery/communication substrate + AgentWeave selection/execution |
| **Custom Python** | `StaticToolCatalog` + `CallableExecutor` or custom protocol implementations |

Optional integration installs:

```bash
pip install 'agentweave-router[mcp]'
pip install 'agentweave-router[langgraph]'
pip install 'agentweave-router[autogen]'
pip install 'agentweave-router[all-integrations]'
```

Real upstream MCP, LangGraph, and AutoGen packages are installed in a dedicated compatibility CI matrix. MCP compatibility additionally executes an in-process real MCP server/client end-to-end path, including duplicate native tool names across servers. Built-wheel smoke tests separately verify that base and integration extras install correctly outside the source checkout.

## Results at a glance

> The headline BFCL result is a **BFCL-derived routing-pressure experiment, not an official full BFCL leaderboard score**.

| Evidence | Verified result |
|---|---|
| BFCL routing-pressure v6 | **6/48 native task successes vs 0/48 for matched all-tools, random top-8, and semantic top-8 baselines** |
| Tool exposure | **70.18% fewer** than all-tools |
| Input tokens | **61.70% fewer** than all-tools |
| Mean local-model latency | **50.95% lower** than all-tools |
| Statistical test | Exact McNemar **p = 0.03125** |
| AgentBench | **52.0% Hit@1; 89.9% accuracy on committed routes at 46.3% coverage** |
| ToolBench | **35.8% Hit@1; 47.5% Hit@3; 53.8% Hit@5; MRR 0.440** |
| AgencyBench | Up to **92.2% cumulative-context Hit@3** |
| Executable team benchmark | **100% completion; 0.937 mean quality; 100% recovery** in the preregistered repeated-seed study |
| Synthetic scale exercised | Up to **1,000,000 agents** |

The BFCL-derived v6 study uses 48 BFCL V4 `multiple` tasks, 16-tool pressure, and a pinned local model. The absolute **12.5% native task success rate** is intentionally retained alongside the relative improvements.

[Reproduce the study](docs/BFCL_REPRODUCE.md) · [Frozen v6 results](BFCL_V6_RESULTS.md) · [Read the paper](https://arxiv.org/abs/2608.23078)

## Research evidence

AgentWeave keeps routing, process-verification, executable-outcome, BFCL-derived, controlled-proxy, and provider-backed evidence separate rather than combining unlike metrics into one score.

| Evidence | Evaluation problem | Current result |
|---|---|---|
| **AgentBench** | Blind specialist selection | **52.0% Hit@1**; **89.9% accuracy on committed routes** at **46.3% coverage** |
| **ToolBench** | Tool/API retrieval over 4,856 APIs | **35.8% Hit@1**, **47.5% Hit@3**, **53.8% Hit@5**, MRR **0.440** |
| **AgencyBench** | Capability-family routing | **57.0% zero-shot Hit@1**; **67.2% cumulative-context Hit@1**; **92.2% cumulative-context Hit@3** |
| **AgentProcessBench** | Label-blind process verification | **55.88% step micro accuracy**; **38.30% first-error accuracy** across **1,000 trajectories / 8,509 steps** |
| **BFCL routing-pressure v6** | Native BFCL validity under augmented tool pressure | **6/48 = 12.5% AgentWeave vs 0/48 for all matched baselines**, exact McNemar **p = 0.03125** |
| **Executable team benchmark** | Controlled multi-agent completion and recovery | **100% completion**, **0.937 mean quality**, **100% recovery** in the preregistered repeated-seed study |

The controlled Issue #38 hybrid-selection artifact remains a deterministic proxy study. `evaluation/issue38_live.py` is a separate real-provider protocol for measuring provider-reported token usage, wall-clock latency, four routing strategies, and hybrid ablations. A validated protocol is **not** itself evidence that a credentialed provider run occurred; see [`docs/ISSUE38_LIVE_PROVIDER.md`](docs/ISSUE38_LIVE_PROVIDER.md).

### Frozen-router generalization

New router versions are evaluated on newly introduced untouched holdouts and then frozen. Percentages across rows are not directly comparable; the valid comparison is the previous router versus the new router on the same new holdout.

| Evaluation | Tasks | Same-holdout result |
|---|---:|---:|
| Frozen original router | 499 | **15.6% Hit@1**; majority baseline 39.9% |
| Router V2 | 72 | 52.8% → **54.2% Hit@1** |
| Router V3 | 72 | 31.9% → **76.4% Hit@1** |
| Router V4 | 72 | 72.2% → **91.7% Hit@1** |
| Router V5 | 72 | 38.9% → **77.8% interactive Hit@1** |
| Router V6 | 72 | 37.5% → **59.7% interactive Hit@1** |
| Router V7 | 72 | 73.6% → **91.7% search-family Hit@1** |

## Scientific boundaries

- Scored studies are frozen after scoring.
- Weak and negative results are retained.
- New router versions use newly introduced holdouts.
- BFCL-derived evidence is not described as an official BFCL leaderboard result.
- Controlled synthetic execution is not described as production performance.
- Routing accuracy is not presented as native task completion.
- The Issue #38 controlled proxy artifact and real-provider artifacts are reported separately; provider/model/date/trial settings must accompany provider-backed claims.
- Host-specific 100k-tool scale measurements are engineering evidence, not universal latency or memory guarantees.
- Changes to model, sample, router, distractors, or protocol require a new study.

The paper-quality evaluation also retains the post-hoc result that simple zero-shot embedding baselines outperform the original frozen AgentWeave router on the already-observed General-AgentBench set.

## Reliability and security

AgentWeave supports failure detection, trust updates, reranking, replacement selection, bounded retry, durable checkpoint/resume workflows, and fail-closed execution authorization.

The proof suite covers malicious Agent Cards, prompt injection, data exfiltration, SSRF/link-local access, tool abuse, spoofing, Sybil/collusion, reputation poisoning, Byzantine disagreement, malformed results, malformed tool-call JSON, invalid tool schemas, argument escalation, hidden high-risk tool selection, and timeouts. It also exercises Docker isolation, JWT Verifiable Credentials, revocation, key rotation, KMS/HSM boundaries, PostgreSQL concurrency, governance constraints, and chaos scenarios.

A passing proof is evidence for the configured test runtime; it is not a formal security, HA, hardware-attestation, or compliance certification.

## CLI

```bash
agentweave version
agentweave doctor
agentweave plugins
agentweave --config agentweave.yaml config-check
agentweave --config agentweave.yaml run "Research and verify this topic"
```

Legacy multi-agent orchestration remains available during the pre-1.0 migration, but new applications should start with `AgentWeaveRuntime` / `AgentWeaveApplication`. See [`docs/API_COMPATIBILITY.md`](docs/API_COMPATIBILITY.md).

## Documentation

| Area | Documentation |
|---|---|
| 0.7 quickstart | [`docs/QUICKSTART_0_7.md`](docs/QUICKSTART_0_7.md) |
| MCP | [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md) |
| A2A interoperability | [`docs/A2A_COMPATIBILITY.md`](docs/A2A_COMPATIBILITY.md) |
| LangGraph | [`docs/LANGGRAPH_INTEGRATION.md`](docs/LANGGRAPH_INTEGRATION.md) |
| AutoGen | [`docs/AUTOGEN_INTEGRATION.md`](docs/AUTOGEN_INTEGRATION.md) |
| Issue #38 real-provider protocol | [`docs/ISSUE38_LIVE_PROVIDER.md`](docs/ISSUE38_LIVE_PROVIDER.md) |
| Road to 1.0 | [`docs/ROAD_TO_1_0.md`](docs/ROAD_TO_1_0.md) |
| BFCL reproduction | [`docs/BFCL_REPRODUCE.md`](docs/BFCL_REPRODUCE.md) |
| API compatibility | [`docs/API_COMPATIBILITY.md`](docs/API_COMPATIBILITY.md) |
| Research paper | [`PAPER.md`](PAPER.md) · [arXiv:2608.23078](https://arxiv.org/abs/2608.23078) |
| Software archive | [Zenodo v0.7.0](https://zenodo.org/records/22913460) · [DOI: 10.5281/zenodo.22913460](https://doi.org/10.5281/zenodo.22913460) |
| Research citation | [`CITATION.cff`](CITATION.cff) |

## Project status

AgentWeave is an **active research and engineering project**. APIs and evaluation protocols may evolve; pin a release or commit when using results in reproducible experiments.

The strongest current evidence is around pre-inference routing, interoperability, recovery, and reproducible evaluation. Published benchmark claims remain scoped to their documented models, datasets, protocols, and test environments. The proposed pre-1.0 freeze discipline and evidence gates are in [`docs/ROAD_TO_1_0.md`](docs/ROAD_TO_1_0.md).

## Contributing

External reproductions are especially valuable. If you test AgentWeave on your own MCP server, tool catalog, agent framework, or benchmark, please open an issue or PR with what worked, what failed, and the catalog size.

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), [`CHANGELOG.md`](CHANGELOG.md), and [`CITATION.cff`](CITATION.cff).

## Paper and software citation

**Research paper:**  
**AgentWeave: Routing Before Reasoning for Efficient Function Calling in Tool-Rich Language Models**  
[arXiv:2608.23078](https://arxiv.org/abs/2608.23078) · [`PAPER.md`](PAPER.md)

**Archived software:**  
**AgentWeave v0.7.0** · [DOI: 10.5281/zenodo.22913460](https://doi.org/10.5281/zenodo.22913460) · [Zenodo record](https://zenodo.org/records/22913460)

If you use AgentWeave in research, cite the paper for the research contribution and the Zenodo DOI when citing or reproducing the archived v0.7.0 software release.

## License

Apache-2.0
