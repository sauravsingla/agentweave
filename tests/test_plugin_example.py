import importlib.metadata
import socket

import pytest

from agentweave.plugins import ComponentRegistry, PluginManager
from examples.plugin_example import ExamplePlugin


@pytest.mark.asyncio
async def test_plugin_example_registers_router_and_runs_hooks_offline(monkeypatch):
    def unexpected_external_access(*args, **kwargs):
        raise AssertionError("The plugin example must not use the network or discover plugins")

    monkeypatch.setattr(socket.socket, "connect", unexpected_external_access)
    monkeypatch.setattr(importlib.metadata, "entry_points", unexpected_external_access)

    plugin = ExamplePlugin()
    registry = ComponentRegistry()
    manager = PluginManager(registry=registry)
    # Registration checks the declared API version against the runtime contract.
    assert manager.register(plugin.name, plugin) is plugin
    assert manager.configure() is registry
    assert list(registry.routers) == ["example-router"]
    assert registry.get("routers", "example-router") is registry.routers["example-router"]
    assert registry.get("routers", "example-router") is not None

    await plugin.start(object())
    await plugin.stop()
