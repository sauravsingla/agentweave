# AgentWeave — Route Before You Reason

[![CI](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml/badge.svg)](https://github.com/sauravsingla/agentweave/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agentweave-router.svg)](https://pypi.org/project/agentweave-router/)
[![GHCR](https://img.shields.io/badge/GHCR-agentweave-blue?logo=github)](https://github.com/sauravsingla/agentweave/pkgs/container/agentweave)
[![Python](https://img.shields.io/pypi/pyversions/agentweave-router.svg)](https://pypi.org/project/agentweave-router/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://github.com/sauravsingla/agentweave/blob/main/LICENSE)
[![Concept DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22913459.svg)](https://doi.org/10.5281/zenodo.22913459)
[![Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Dataset-FFD21E)](https://huggingface.co/datasets/sauravsingla08/AgentWeave-Tool-Routing)

**Pre-inference tool routing for MCP and tool-rich LLM agents. Reduce what the model sees before function calling.**

```text
100+ permitted tools → route before inference → up to 8 model-visible tools by default → validate → authorize → execute
```

AgentWeave is a provider-neutral **LLM tool-routing and policy-aware function-calling and execution boundary** for MCP, A2A, LangGraph, AutoGen, and custom tool catalogs. Deterministic scope comes first; task-aware routing operates only on the permitted remainder, and model-selected calls still pass schema validation and authorization before execution.

**PyPI:** `agentweave-router` · **Python import:** `agentweave`

**Frozen BFCL-derived v6:** **6/48 native task successes vs 0/48 for matched baselines** · **70.18% fewer tools exposed** · **61.70% fewer input tokens** · **50.95% lower mean local-model latency**  
*Routing-pressure experiment on a pinned local model; not an official full BFCL leaderboard score.*

**Quick links:** [30-second install](#30-second-install) · [Local routing demo](#run-real-routing-locally-no-api-keys) · [MCP](#mcp-quickstart) · [Results](#results-at-a-glance) · [Documentation](#documentation) · [Contribute](https://github.com/sauravsingla/agentweave/blob/main/CONTRIBUTING.md) · [Road to 1.0](https://github.com/sauravsingla/agentweave/blob/main/docs/ROAD_TO_1_0.md) · [Hugging Face Dataset](https://huggingface.co/datasets/sauravsingla08/AgentWeave-Tool-Routing) · [Paper](https://arxiv.org/abs/2608.23078)

## 100,000-tool demo

[![AgentWeave 100,000-tool demo](https://raw.githubusercontent.com/sauravsingla/agentweave/main/assets/agentweave_100k_tools_demo_preview.gif)](https://github.com/sauravsingla/agentweave/blob/main/assets/agentweave_100k_tools_silent_demo.mp4)

*Synthetic engineering-scale demonstration; not a production latency, memory, or capacity guarantee.*

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
replay / idempotency guard
  ↓
execution
  ↓
bounded recovery / rediscovery
```

AgentWeave does **not** replace MCP, LangGraph, AutoGen, A2A, or your model. It provides a provider-neutral routing and execution boundary around them.

## 30-second install

Install the base package from PyPI (Python 3.11+), then verify the CLI:

```bash
python -m pip install agentweave-router
agentweave version
agentweave doctor
```

The PyPI distribution is `agentweave-router`; Python imports use `agentweave`. The base install does not require MCP, LangGraph, AutoGen, or provider credentials.

### Run real routing locally (no API keys)

The repository includes a deterministic [local example](https://github.com/sauravsingla/agentweave/blob/main/examples/local_runtime.py) that exercises the real `AgentWeaveRuntime` routing, validation, authorization, and execution path with three tools and a scripted model:

```bash
git clone https://github.com/sauravsingla/agentweave.git
cd agentweave
python -m pip install -e .
python examples/local_runtime.py
```

It routes an addition request to `add_numbers`, prints the catalog, routed set, and model-visible tools, then executes the selected function and returns 42. No external model, MCP server, API key, or network service is required after installation.

> ⭐ **If AgentWeave is useful in your tool-routing or MCP work, a GitHub star helps other developers discover the project.**

## MCP quickstart

Install the MCP extra:

```bash
python -m pip install 'agentweave-router[mcp]'
```

Connect your model endpoint and MCP server. `base_url` is the OpenAI-compatible API root; AgentWeave appends `/chat/completions`:

```python
import asyncio

from agentweave import AgentWeaveApplication
from agentweave_byom import OpenAICompatibleModelAdapter


async def main() -> None:
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
    print(result.status)


if __name__ == "__main__":
    asyncio.run(main())
```

`AgentWeaveApplication` owns the MCP/runtime/plugin lifecycle. AgentWeave handles discovery, scope policy, routing, schema validation, argument-aware authorization, execution, bounded recovery, provenance, and telemetry. A one-shot `app.run(...)` manages startup and shutdown automatically; for repeated calls, keep the lifecycle open with `async with app:`.

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

If both servers expose native `search`, the model sees collision-safe names such as `billing__search` and `crm__search`, while execution is dispatched by canonical tool identity and each MCP server still receives its native tool name.

A self-contained [multi-MCP collision example](https://github.com/sauravsingla/agentweave/blob/main/examples/multi_mcp_collision.py) is included in the repository:

```bash
python -m pip install -e '.[mcp]'
python examples/multi_mcp_collision.py
```

It starts two in-process MCP servers and verifies one native `search` call reaches each provider. No external model or network service is required.

## Why AgentWeave?

Use AgentWeave when a model or agent can access a **large heterogeneous catalog of tools or specialist agents** and the model-visible action space should be reduced before inference.

- **Route before inference:** reduce the set of tools the model has to reason over.
- **Scope before routing:** role, tenant, permission, and policy constraints are applied before task-aware selection.
- **Validate and authorize after selection:** routing a tool does not grant permission to execute it.
- **Keep tool identity explicit:** provider/source identity is separate from the name shown to the model.
- **Stay provider-neutral:** use MCP, LangGraph, AutoGen, A2A, custom catalogs, or custom model adapters without making routing provider-specific.

Typical use cases include large MCP catalogs, enterprise capability catalogs, multi-agent specialist pools, A2A ecosystems, LangGraph workflows, AutoGen teams, marketplaces, cloud agents, and edge runtimes.

If deterministic scope already reduces the catalog sufficiently, apply that first. AgentWeave's task-aware routing operates only on the permitted remainder.

## Canonical runtime and execution boundary

`AgentWeaveRuntime` is the primary 0.7+ execution surface:

```text
catalog → scope → route → model → validate arguments → authorize → replay guard → execute → recover
```

Key normalized contracts are `ToolSpec`, `ToolCall`, `ToolResult`, `ModelResponse`, `RunContext`, and `RuntimeResult`.

The canonical runtime enforces the following boundaries:

- model-visible aliases cannot silently collapse distinct provider/source identities;
- model-generated arguments are validated against `ToolSpec.input_schema` before authorization or execution;
- calls outside the routed/model-visible set fail closed;
- authorization policies receive resolved tool identity, arguments, provider/source metadata, and runtime security context;
- replay/idempotency protection runs after authorization and caches only successful executions;
- executor-returned identity cannot override the canonical tool identity that passed routing, validation, and authorization;
- per-stage telemetry records catalog, scope/routing, model, validation, authorization, replay, execution, and recovery timing/provenance.

`ToolSpec.idempotency` supports `auto`, `none`, `call_id`, and `arguments`; `auto` uses argument-signature protection for high/critical-risk tools and call-ID protection for other tools.

For AgentWeave-owned HTTP traffic, `SafeHttpTransport` provides endpoint validation, DNS pinning/rebinding checks, guarded redirects, Host/SNI preservation, and cross-origin credential stripping. For MCP connections, the MCP SDK still owns the protocol wire transport unless the application supplies a custom client factory; AgentWeave validates the target before connection establishment rather than claiming ownership of the MCP SDK's transport.

These are runtime controls and tested boundaries, not a formal security, compliance, or hardware-attestation certification.

### Application and configuration

`AgentWeaveApplication` owns runtime and plugin startup/shutdown as one async boundary. Plugin startup is version-checked and transactional, so a partial startup failure is rolled back.

JSON configuration works with the base package. YAML configuration requires the optional YAML extra:

```bash
python -m pip install 'agentweave-router[yaml]'
```

```python
import asyncio

from agentweave import AgentWeaveApplication


async def main() -> None:
    app = AgentWeaveApplication.from_file("agentweave.yaml")
    result = await app.run("Find the invoice and verify it")
    print(result.status)


if __name__ == "__main__":
    asyncio.run(main())
```

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
python -m pip install 'agentweave-router[mcp]'
python -m pip install 'agentweave-router[langgraph]'
python -m pip install 'agentweave-router[autogen]'
python -m pip install 'agentweave-router[all-integrations]'
```

Real upstream MCP, LangGraph, and AutoGen packages are installed in a dedicated compatibility CI matrix. MCP compatibility additionally executes an in-process real MCP server/client end-to-end path, including duplicate native tool names across servers. Built-wheel smoke tests separately verify that base and integration extras install correctly outside the source checkout.

## Container image (GHCR)

The base AgentWeave CLI image is published to GitHub Container Registry:

```bash
docker pull ghcr.io/sauravsingla/agentweave:latest
docker run --rm ghcr.io/sauravsingla/agentweave:latest version
```

The image runs as an unprivileged user and uses `/workspace` as its writable working directory. The `agentweave` CLI is the image entry point, so subcommands can be passed directly:

```bash
docker run --rm ghcr.io/sauravsingla/agentweave:latest plugins
docker run --rm ghcr.io/sauravsingla/agentweave:latest doctor
```

For reproducible use, prefer an immutable digest or a release tag rather than `latest`. See [`docs/CONTAINER.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/CONTAINER.md) for persistent volumes, configuration mounts, published tags, and image design.

## Results at a glance

> The headline BFCL result is a **BFCL-derived routing-pressure experiment, not an official full BFCL leaderboard score**.

| Evidence | Verified result |
|---|---|
| BFCL routing-pressure v6 | **6/48 = 12.5% native task success vs 0/48 for matched all-tools, random top-8, and semantic top-8 baselines**; exact McNemar **p = 0.03125** |
| BFCL efficiency vs all-tools | **70.18% fewer tools exposed**, **61.70% fewer input tokens**, **50.95% lower mean local-model latency** |
| AgentBench | **52.0% Hit@1; 89.9% accuracy on committed routes at 46.3% coverage** |
| ToolBench | **35.8% Hit@1; 47.5% Hit@3; 53.8% Hit@5; MRR 0.440** |
| AgencyBench | Up to **92.2% cumulative-context Hit@3** |
| AgentProcessBench | **55.88% step micro accuracy; 38.30% first-error accuracy** across **1,000 trajectories / 8,509 steps** |
| Executable team benchmark | **100% completion; 0.937 mean quality; 100% recovery** in the preregistered repeated-seed study |

The BFCL-derived v6 study uses 48 fresh BFCL V4 `multiple` tasks, 16-tool pressure, and a pinned local model. The absolute success rate is shown alongside the relative efficiency improvements rather than reporting the relative gains alone.

[Reproduce the BFCL study](https://github.com/sauravsingla/agentweave/blob/main/docs/BFCL_REPRODUCE.md) · [Frozen v6 results](https://github.com/sauravsingla/agentweave/blob/main/BFCL_V6_RESULTS.md) · [Research paper](https://arxiv.org/abs/2608.23078) · [`PAPER.md`](https://github.com/sauravsingla/agentweave/blob/main/PAPER.md)

### Research boundaries

AgentWeave keeps routing, process-verification, executable-outcome, BFCL-derived, controlled-proxy, and provider-backed evidence separate rather than combining unlike metrics into one score.

- Scored studies are frozen after scoring; weak and negative results are retained.
- New router versions use newly introduced untouched holdouts.
- Controlled synthetic execution is not described as production performance.
- Routing accuracy is not presented as native task completion.
- The controlled Issue #38 proxy and real-provider protocol remain separate; a validated protocol is not evidence that a credentialed provider run occurred.
- Host-specific scale measurements are engineering evidence, not universal latency or memory guarantees.
- Changes to model, sample, router, distractors, or protocol require a new study.

The paper-quality evaluation also retains the post-hoc result that simple zero-shot embedding baselines outperform the original frozen AgentWeave router on the already-observed General-AgentBench set.

See [`docs/ISSUE38_LIVE_PROVIDER.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/ISSUE38_LIVE_PROVIDER.md), [`docs/ROAD_TO_1_0.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/ROAD_TO_1_0.md), and the frozen artifacts under `evaluation/` for detailed protocols and holdout histories.

## CLI

```bash
agentweave version
agentweave doctor
agentweave plugins
```

Runtime configuration commands require a config file. For YAML configs, install `agentweave-router[yaml]` first:

```bash
agentweave --config agentweave.yaml config-check
agentweave --config agentweave.yaml run "Research and verify this topic"
```

Legacy multi-agent orchestration remains available during the pre-1.0 migration, but new applications should start with `AgentWeaveRuntime` / `AgentWeaveApplication`. See [`docs/API_COMPATIBILITY.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/API_COMPATIBILITY.md).

## Documentation

| Area | Documentation |
|---|---|
| 0.7 quickstart | [`docs/QUICKSTART_0_7.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/QUICKSTART_0_7.md) |
| Container image | [`docs/CONTAINER.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/CONTAINER.md) |
| MCP | [`docs/MCP_INTEGRATION.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/MCP_INTEGRATION.md) |
| A2A interoperability | [`docs/A2A_COMPATIBILITY.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/A2A_COMPATIBILITY.md) |
| LangGraph | [`docs/LANGGRAPH_INTEGRATION.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/LANGGRAPH_INTEGRATION.md) |
| AutoGen | [`docs/AUTOGEN_INTEGRATION.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/AUTOGEN_INTEGRATION.md) |
| Issue #38 real-provider protocol | [`docs/ISSUE38_LIVE_PROVIDER.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/ISSUE38_LIVE_PROVIDER.md) |
| Road to 1.0 | [`docs/ROAD_TO_1_0.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/ROAD_TO_1_0.md) |
| BFCL reproduction | [`docs/BFCL_REPRODUCE.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/BFCL_REPRODUCE.md) |
| API compatibility | [`docs/API_COMPATIBILITY.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/API_COMPATIBILITY.md) |
| Research paper | [`PAPER.md`](https://github.com/sauravsingla/agentweave/blob/main/PAPER.md) · [arXiv:2608.23078](https://arxiv.org/abs/2608.23078) |
| Evolving software project | [Concept DOI: 10.5281/zenodo.22913459](https://doi.org/10.5281/zenodo.22913459) |
| Archived v0.7.0 software | [Zenodo v0.7.0](https://zenodo.org/records/22913460) · [Version DOI: 10.5281/zenodo.22913460](https://doi.org/10.5281/zenodo.22913460) |
| Research citation | [`CITATION.cff`](https://github.com/sauravsingla/agentweave/blob/main/CITATION.cff) |

## Project status

AgentWeave is an **active research and engineering project**. APIs and evaluation protocols may evolve; pin a release or commit when using results in reproducible experiments.

The strongest current evidence is around pre-inference routing, interoperability, recovery, and reproducible evaluation. Published benchmark claims remain scoped to their documented models, datasets, protocols, and test environments. The proposed pre-1.0 freeze discipline and evidence gates are in [`docs/ROAD_TO_1_0.md`](https://github.com/sauravsingla/agentweave/blob/main/docs/ROAD_TO_1_0.md).

## Contributing

External reproductions are especially valuable. If you test AgentWeave on your own MCP server, tool catalog, agent framework, or benchmark, please open an issue or PR with what worked, what failed, and the catalog size.

See [`CONTRIBUTING.md`](https://github.com/sauravsingla/agentweave/blob/main/CONTRIBUTING.md), [`SECURITY.md`](https://github.com/sauravsingla/agentweave/blob/main/SECURITY.md), [`CHANGELOG.md`](https://github.com/sauravsingla/agentweave/blob/main/CHANGELOG.md), and [`CITATION.cff`](https://github.com/sauravsingla/agentweave/blob/main/CITATION.cff).

## Paper and software citation

**Research paper:**  
**AgentWeave: Routing Before Reasoning for Efficient Function Calling in Tool-Rich Language Models**  
[arXiv:2608.23078](https://arxiv.org/abs/2608.23078) · [`PAPER.md`](https://github.com/sauravsingla/agentweave/blob/main/PAPER.md)

**Evolving software project:**  
**AgentWeave — Concept DOI:** [10.5281/zenodo.22913459](https://doi.org/10.5281/zenodo.22913459)

**Archived software release:**  
**AgentWeave v0.7.0** · [Version DOI: 10.5281/zenodo.22913460](https://doi.org/10.5281/zenodo.22913460) · [Zenodo record](https://zenodo.org/records/22913460)

Use the arXiv paper for the research contribution, the Concept DOI for the evolving AgentWeave software project, and the version DOI when citing or reproducing the archived v0.7.0 release.

## License

Apache-2.0