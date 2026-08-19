from __future__ import annotations

import asyncio

from agentweave_byom import BYOMAgentWeave, CallableModelAdapter

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "weather_forecast",
            "description": "Get a weather forecast for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a recipient",
            "parameters": {
                "type": "object",
                "properties": {"to": {"type": "string"}, "body": {"type": "string"}},
            },
        },
    },
]


async def my_model(*, messages, tools, **kwargs):
    # Replace this function with any provider SDK call. AgentWeave passes only the
    # routed tool subset to it.
    return {
        "model_received": messages[-1]["content"],
        "visible_tools": [tool["function"]["name"] for tool in tools],
    }


async def main():
    weave = BYOMAgentWeave(
        model=CallableModelAdapter(my_model, name="my-model"),
        tools=TOOLS,
        db_path=":memory:",
    )
    result = await weave.run("What is the weather in Delhi?", max_tools=1)
    print(result["response"])
    print(result["routing_provenance"])


if __name__ == "__main__":
    asyncio.run(main())
