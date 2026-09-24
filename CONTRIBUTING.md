# Contributing to AgentWeave

Contributions are welcome across protocol interoperability, trust/identity, agent matching, graph optimization, edge runtimes, security, evaluation and documentation.

## New contributor? Start here

AgentWeave keeps a small set of intentionally bounded issues so contributors can learn the codebase without taking on a large subsystem. Pick the tier that best matches how deeply you want to work in the runtime.

### Good first issue

- [#59 — Add an examples index with run commands and expected behavior](https://github.com/sauravsingla/agentweave/issues/59) — documentation-focused onboarding work covering the existing examples, dependencies, commands and network/credential requirements.

### Intermediate issues

- [#65 — Add configurable timeout handling for tool execution](https://github.com/sauravsingla/agentweave/issues/65) — follow the execution path and add bounded timeout behavior with focused tests.
- [#66 — Add machine-readable reason codes for rejected tool calls](https://github.com/sauravsingla/agentweave/issues/66) — improve structured failure reporting across parsing, validation, authorization and execution boundaries.
- [#67 — Add opt-in bounded parallel execution for independent tool calls](https://github.com/sauravsingla/agentweave/issues/67) — add async concurrency while preserving authorization, deterministic ordering and sequential defaults.
- [#68 — Make runtime shutdown resilient when component cleanup fails](https://github.com/sauravsingla/agentweave/issues/68) — harden lifecycle cleanup, exception handling and reverse-order shutdown behavior.

Comment on the issue if you want to coordinate before starting. For concrete design or usage questions that do not yet belong in an issue, use [GitHub Discussions](https://github.com/sauravsingla/agentweave/discussions) — useful topics include MCP/A2A interoperability, framework integrations, benchmark reproduction, routing behavior and tool-catalog design. Security reports should still follow `SECURITY.md`.

## Development setup

```bash
python -m pip install -e '.[dev]'
pytest -q
```

The normal test suite checks repository-relative Markdown links without fetching
external URLs. Run `pytest -q tests/test_markdown_links.py` for just this check.
It validates inline links, images and reference definitions against local paths;
anchor fragments are not checked. Links to generated `docs/*.html` pages are
checked against their Markdown sources.

For native C++ tests:

```bash
python -m pip install pybind11
cmake -S cpp -B cpp/build -DAGENTWEAVE_BUILD_PYBIND=ON -Dpybind11_DIR=$(python -m pybind11 --cmakedir)
cmake --build cpp/build
PYTHONPATH=cpp/build python -c "import _agentweave_core"
```

## Pull requests

Keep changes scoped, include tests for behavior changes, document public API changes, and do not weaken fail-closed security checks merely to make an integration pass. External proofs must distinguish a configured harness from a proof that was actually executed.

Public API changes must follow `docs/API_COMPATIBILITY.md`. User-visible changes should update `CHANGELOG.md` under `Unreleased` unless they are part of a release preparation change.

## Research contributions

Benchmark changes should preserve fixed seeds or clearly version the dataset/methodology. Do not relabel capped or sampled experiments as larger physical runs. Include raw result artifacts or enough information to regenerate them.

## Security

Do not submit real secrets, production credentials or private endpoint tokens. Follow `SECURITY.md` for vulnerability reporting.
