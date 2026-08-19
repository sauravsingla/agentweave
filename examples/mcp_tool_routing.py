"""Route an MCP tool catalog with AgentWeave before exposing tools to a model.

This example intentionally works on plain MCP `tools/list`-style dictionaries so it does
not require an MCP transport/runtime. It demonstrates the integration boundary:

MCP tool catalog -> AgentWeave router -> smaller model-visible MCP tool catalog

Run from the repository root after installing the study routing dependency:

    pip install -e .
    pip install 'sentence-transformers>=5.1,<6'
    python examples/mcp_tool_routing.py
"""

from __future__ import annotations

from typing import Any

from scripts.bfcl_routing_proxy import Router


def mcp_to_router_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Adapt an MCP tool descriptor to the router's function-tool shape."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
        },
        "_mcp_original": tool,
    }


def route_mcp_tools(
    user_text: str,
    tools: list[dict[str, Any]],
    *,
    max_provider_groups: int = 3,
    max_tools: int = 6,
) -> list[dict[str, Any]]:
    """Return the exact MCP tool descriptors selected for model exposure."""
    adapted = [mcp_to_router_tool(tool) for tool in tools]
    router = Router(
        "agentweave",
        max_agents=max_provider_groups,
        max_tools=max_tools,
    )
    selected = router.select([{"role": "user", "content": user_text}], adapted)
    return [tool["_mcp_original"] for tool in selected]


def main() -> None:
    # Representative MCP `tools/list` descriptors. A real client would use the list
    # returned by its connected MCP servers.
    tools = [
        {
            "name": "github_search_code",
            "description": "Search source code in GitHub repositories.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "github_create_issue",
            "description": "Create a GitHub issue in a repository.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repository": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["repository", "title"],
            },
        },
        {
            "name": "calendar_find_events",
            "description": "Find calendar events in a date range.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "calendar_create_event",
            "description": "Create a calendar event.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "gmail_search_messages",
            "description": "Search email messages.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "gmail_send_message",
            "description": "Send an email message.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "weather_forecast",
            "description": "Get a weather forecast for a location.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "maps_search_places",
            "description": "Search for nearby places and businesses.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]

    request = "Open an issue in the AgentWeave GitHub repository about routing provenance."
    selected = route_mcp_tools(request, tools, max_provider_groups=3, max_tools=4)

    print(f"Source MCP tools: {len(tools)}")
    print(f"Model-visible tools after AgentWeave routing: {len(selected)}")
    for tool in selected:
        print(f"- {tool['name']}: {tool.get('description', '')}")


if __name__ == "__main__":
    main()
