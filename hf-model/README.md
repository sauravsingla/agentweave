---
license: apache-2.0
tags:
  - agentweave
  - agentic-ai
  - tool-routing
  - semantic-routing
  - function-calling
  - cpu
  - minilm
  - sentence-transformers
  - pre-inference-routing
  - arxiv:2608.23078
language:
  - en
datasets:
  - sauravsingla08/AgentWeave-Tool-Routing
---

# AgentWeave Router MiniLM 🧭

> **Route before you reason.**

A lightweight, CPU-first semantic capability router for **AgentWeave**. It uses `sentence-transformers/all-MiniLM-L6-v2` as a frozen embedding encoder and ranks route prototypes with cosine similarity before downstream model inference.

This repository is intentionally small: it publishes the AgentWeave routing configuration, route prototypes, and executable router code while reusing the upstream MiniLM encoder at runtime instead of copying its weights.

## Artifact type and dependency boundary

This Hub repository is a **routing artifact**, not a derived MiniLM checkpoint.

- No MiniLM weights are included in this repository.
- No fine-tuning, adapter training, quantization, merge, or weight transformation is claimed.
- `sentence-transformers/all-MiniLM-L6-v2` is downloaded separately at runtime and used as a **frozen encoder dependency**.
- AgentWeave-specific behavior comes from the route taxonomy, human-readable prototypes, and cosine-ranking logic published here.

For that reason the Hub metadata intentionally does not declare this repository as a `base_model` derivative or as a standalone SentenceTransformers checkpoint.

## Why this exists

Tool-rich agents can expose large action spaces to a language model. AgentWeave explores a complementary systems strategy: reduce the candidate action space *before* model reasoning. This model repository provides an experimental semantic routing companion to AgentWeave's default deterministic routing path.

### Route families

- 🔎 `research`
- 📚 `retrieval`
- 🧠 `analysis`
- 💻 `coding`
- 🗺️ `planning`
- ✅ `verification`
- 📝 `summarization`
- 📊 `data_analysis`

## Architecture

```text
Task / user request
        │
        ▼
all-MiniLM-L6-v2
frozen 384-d encoder
        │
        ├──────────────┐
        ▼              ▼
query vector     route prototypes
        │              │
        └──── cosine ──┘
               │
               ▼
        ranked route set
               │
               ▼
      downstream AgentWeave
```

**No fine-tuning is claimed.** This is a prototype-based semantic router built on a frozen MiniLM encoder. Similarity scores are ranking signals, **not calibrated probabilities**.

## Quick start

Clone or download the files in this repository, then run:

```bash
pip install -r requirements.txt
python router.py "research the latest protocol changes, verify the sources, and summarize the findings"
```

Example output shape:

```json
[
  {"route": "research", "score": 0.0},
  {"route": "verification", "score": 0.0},
  {"route": "summarization", "score": 0.0}
]
```

The numeric values above are placeholders showing the response schema; actual scores are computed locally from MiniLM embeddings.

## Python usage

```python
from router import AgentWeaveSemanticRouter

router = AgentWeaveSemanticRouter()
routes = router.route(
    "inspect this code, identify correctness risks, and propose a fix",
    top_k=3,
)
print(routes)
```

## CPU-first design

The router is designed for lightweight local execution:

- frozen MiniLM encoder
- no text generation
- no external inference API required
- normalized embeddings + cosine ranking
- small route-prototype file

The first run downloads the upstream MiniLM encoder. Subsequent runs can use the local Hugging Face cache.

## Relationship to AgentWeave

AgentWeave's documented default BYOM routing path is deterministic and provider-neutral. This MiniLM router is an **experimental semantic companion**, not a replacement for the default router and not the source of AgentWeave's published deterministic-router benchmark claims.

Relevance routing also does **not** grant permission to execute a tool. Policy filtering, scope controls, and authorization remain separate boundaries in AgentWeave.

## Files

| File | Purpose |
|---|---|
| `router.py` | CPU semantic router implementation |
| `route_prototypes.json` | Human-readable capability prototypes |
| `config.json` | Frozen encoder dependency and routing configuration |
| `requirements.txt` | Minimal runtime dependencies |

## Intended use

Good fits:

- pre-inference capability routing
- agent/tool candidate reduction experiments
- CPU routing demos
- semantic route exploration
- research comparisons with deterministic routing

Not intended as:

- a calibrated confidence model
- an authorization engine
- a safety classifier
- a standalone MiniLM or SentenceTransformers checkpoint
- a replacement for downstream function-calling evaluation

## Limitations

- English-focused route prototypes
- prototype wording influences ranking
- route scores are cosine similarities, not probabilities
- the route taxonomy is intentionally compact
- domain-specific tools may need custom prototypes

## Related research artifacts

- Paper: https://arxiv.org/abs/2608.23078
- Dataset: https://huggingface.co/datasets/sauravsingla08/AgentWeave-Tool-Routing
- Interactive Space: https://huggingface.co/spaces/sauravsingla08/AgentWeave
- Source: https://github.com/sauravsingla/agentweave

## License

Apache-2.0. The upstream `sentence-transformers/all-MiniLM-L6-v2` model is loaded separately at runtime and remains subject to its own model card and license terms.
