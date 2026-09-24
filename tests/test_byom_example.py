import ast
import socket
import sqlite3

import pytest

from examples.byom_agentweave import main


@pytest.mark.asyncio
async def test_byom_example_routes_weather_without_external_services(monkeypatch, capsys):
    def unexpected_connection(*args, **kwargs):
        raise AssertionError("The BYOM example must not connect to a service")

    connect = sqlite3.connect
    databases = []

    def memory_database(database, *args, **kwargs):
        assert database == ":memory:", "The BYOM example must not create a filesystem database"
        databases.append(database)
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", unexpected_connection)
    monkeypatch.setattr(sqlite3, "connect", memory_database)
    await main()

    response, provenance = [ast.literal_eval(line) for line in capsys.readouterr().out.splitlines()]
    assert databases
    assert response["model_received"] == "What is the weather in Delhi?"
    assert response["visible_tools"] == ["weather_forecast"]
    assert provenance["selected_tools"] == response["visible_tools"]
    assert provenance["filtered_tools"] == ["send_email"]
    assert provenance["catalog_size"] == 2
    assert provenance["max_tools"] == 1
    assert provenance["router"]
    assert provenance["model_adapter"] == "my-model"
