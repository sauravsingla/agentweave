import pytest

from agentweave_byom import BYOMAgentWeave, CallableModelAdapter, ToolRouter


def _tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": "Send an email message to a recipient",
                "parameters": {"type": "object", "properties": {"to": {"type": "string"}}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "weather_forecast",
                "description": "Get a weather forecast for a city",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "database_query",
                "description": "Run a SQL database query",
                "parameters": {"type": "object", "properties": {"sql": {"type": "string"}}},
            },
        },
    ]


def test_tool_router_preserves_original_descriptors_and_records_provenance():
    tools = _tools()
    result = ToolRouter().route("Send an email to the customer", tools, max_tools=1)
    assert result.selected[0] is tools[0]
    assert result.provenance["router"] == "agentweave-tool-router-v1"
    assert result.provenance["catalog_size"] == 3
    assert result.provenance["selected_tools"] == ["send_email"]
    assert len(result.provenance["catalog_sha256"]) == 64


@pytest.mark.asyncio
async def test_byom_agentweave_routes_before_calling_user_model():
    calls = []

    async def fake_model(*, messages, tools, **kwargs):
        calls.append({"messages": messages, "tools": tools, "kwargs": kwargs})
        return {"chosen": tools[0]["function"]["name"]}

    adapter = CallableModelAdapter(fake_model, name="test-model")
    weave = BYOMAgentWeave(model=adapter, tools=_tools(), db_path=":memory:")
    result = await weave.run("What is the weather in Delhi?", max_tools=1)

    assert result["model"] == "test-model"
    assert result["response"] == {"chosen": "weather_forecast"}
    assert len(calls) == 1
    assert [t["function"]["name"] for t in calls[0]["tools"]] == ["weather_forecast"]
    assert result["routing_provenance"]["model_adapter"] == "test-model"
    assert "send_email" in result["routing_provenance"]["filtered_tools"]


def test_callable_adapter_supports_sync_sdk_wrappers():
    adapter = CallableModelAdapter(
        lambda *, messages, tools, **kwargs: {"message_count": len(messages), "tool_count": len(tools or [])},
        name="sync-model",
    )
    assert adapter.identity == "sync-model"
