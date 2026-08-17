# Official BFCL integration path

AgentWeave can be evaluated as a BFCL-compatible routed system without changing BFCL questions, evaluator ground truth, or benchmark function definitions.

This path is intentionally separate from the frozen BFCL routing-pressure v5/v6 studies. Those studies deterministically add distractor functions and therefore are **not official BFCL leaderboard scores**. The integration described here consumes the normal BFCL task/function set exactly as BFCL provides it.

## Upstream basis

The implementation targets Gorilla/BFCL commit:

`6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`

At that revision, BFCL's contribution guide asks new leaderboard submissions to provide a model handler, a `ModelConfig` entry, a supported-model entry, and a `SUPPORTED_MODELS.md` entry. The underlying model/endpoint must be publicly accessible for public leaderboard inclusion.

## Architecture

```text
BFCL task + normal BFCL candidate functions
                  |
                  v
       AgentWeave BFCLToolRouter
       provider grouping + semantic scoring
       + GlobalTeamOptimizer
                  |
                  v
      selected BFCL function subset
                  |
                  v
        BFCL HammerHandler prompt
                  |
                  v
       MadeAgents/Hammer2.1-1.5b
                  |
                  v
        normal BFCL decoder/evaluator
```

The upstream-ready handler is in:

`integrations/bfcl_upstream/agentweave_hammer.py`

The reusable routing implementation is in:

`agentweave/bfcl.py`

## Proposed BFCL model identity

Recommended registry key:

`AgentWeave-Hammer2.1-1.5B`

Recommended display name:

`AgentWeave + Hammer2.1-1.5B (Prompt)`

The submission should clearly identify AgentWeave as a routing/orchestration system layered over the public Hammer model rather than claiming that AgentWeave itself is a foundation model.

## Upstream files

### 1. Model handler

Copy `integrations/bfcl_upstream/agentweave_hammer.py` to:

`berkeley-function-call-leaderboard/bfcl_eval/model_handler/local_inference/agentweave_hammer.py`

The handler subclasses BFCL's existing `HammerHandler` and overrides only `_format_prompt`. It receives BFCL's complete function list and routes that list immediately before prompt construction.

### 2. `model_config.py`

Add the import:

```python
from bfcl_eval.model_handler.local_inference.agentweave_hammer import AgentWeaveHammerHandler
```

Then add an OSS model configuration using:

```python
"AgentWeave-Hammer2.1-1.5B": ModelConfig(
    model_name="MadeAgents/Hammer2.1-1.5b",
    display_name="AgentWeave + Hammer2.1-1.5B (Prompt)",
    url="https://github.com/sauravsingla/agentweave",
    org="AgentWeave / MadeAgents",
    license="See upstream model license",
    model_handler=AgentWeaveHammerHandler,
    input_price=None,
    output_price=None,
    is_fc_model=False,
    underscore_to_dot=False,
),
```

The exact underlying-model license should be copied from the public Hammer model card when the upstream PR is prepared rather than guessed.

### 3. Supported-model registration

Add `AgentWeave-Hammer2.1-1.5B` to BFCL's `bfcl_eval/constants/supported_models.py` and add the corresponding Prompt entry to `SUPPORTED_MODELS.md`, following the ordering/style used by the current file.

### 4. Dependency

The upstream handler imports `agentweave.bfcl.BFCLToolRouter`. Until AgentWeave is available as a stable public package, a reproducible evaluation environment can install the repository directly:

```bash
pip install 'git+https://github.com/sauravsingla/agentweave.git'
pip install 'sentence-transformers>=5.1,<6'
```

For a long-lived upstream contribution, publishing a pinned AgentWeave package release is preferable so BFCL can reproduce the handler without tracking an unpinned branch.

## Routing defaults

The official handler defaults to:

- maximum provider agents: `4`
- maximum model-visible tools: `6`
- embedding model: `sentence-transformers/all-MiniLM-L6-v2`

They may be overridden by:

- `AGENTWEAVE_BFCL_MAX_AGENTS`
- `AGENTWEAVE_BFCL_MAX_TOOLS`
- `AGENTWEAVE_BFCL_EMBEDDING_MODEL`

For any leaderboard submission, these values should be frozen before scoring and reported with the result. They should not be tuned against the BFCL test outcomes.

## Evaluation rule

An official-score attempt must use BFCL's standard generation/evaluation commands and unmodified benchmark data. Do **not** use the v5/v6 distractor augmentation when generating an official submission.

A valid publication sequence is:

1. freeze AgentWeave commit, BFCL commit, routing budget, embedding model, Hammer model revision, and generation settings;
2. run standard BFCL generation over the required official categories;
3. run BFCL's native evaluator without custom ground-truth changes;
4. retain complete outputs, score files, failure records, timing/token metadata, and the exact environment;
5. report the result as `AgentWeave + Hammer2.1-1.5B`, not as a Hammer-only model score;
6. submit the handler/config/supported-model changes and self-evaluated BFCL results upstream.

## Evidence boundary

Until Gorilla/BFCL accepts an upstream PR and the result is reproduced under BFCL's standard publication process, any score generated with this adapter should be described as a **BFCL-compatible standard-data evaluation**, not an official BFCL leaderboard score.
