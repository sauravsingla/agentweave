from agentweave import AgentWeaveRuntime as RootRuntime
from agentweave.runtime import AgentWeaveRuntime as ModuleRuntime
from agentweave.runtime_hardened import AgentWeaveRuntime as HardenedRuntime


def test_direct_runtime_import_uses_canonical_hardened_runtime():
    assert ModuleRuntime is RootRuntime
    assert ModuleRuntime is HardenedRuntime
    assert "arguments" in ModuleRuntime._IDEMPOTENCY_MODES
