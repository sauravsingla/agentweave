# Contributing to AgentWeave

Contributions are welcome across protocol interoperability, trust/identity, agent matching, graph optimization, edge runtimes, security, evaluation and documentation.

## Development setup

```bash
python -m pip install -e '.[dev]'
pytest -q
```

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
