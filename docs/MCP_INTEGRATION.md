# MCP tool-routing integration example

AgentWeave can sit between an MCP tool catalog and the model-facing tool list.

The integration boundary is:

```text
MCP tools/list response
        ↓
AgentWeave pre-inference routing
        ↓
smaller model-visible MCP tool set
        ↓
model tool selection / invocation
```

This does **not** change MCP tool schemas or invocation semantics. It only selects which already-discovered tools are exposed to the model for a given request.

## Why this is useful

MCP servers can expose many tools. A client may want to keep discovery broad while reducing the model-visible action space before inference.

The example in [`examples/mcp_tool_routing.py`](../examples/mcp_tool_routing.py) consumes plain MCP `tools/list`-style descriptors (`name`, `description`, and `inputSchema`), adapts them to AgentWeave's existing routed-function representation, and returns the exact original MCP tool descriptors selected for exposure.

## Run it

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install 'sentence-transformers>=5.1,<6'
python examples/mcp_tool_routing.py
```

The example is local and does not require an MCP server, API key, or model. It demonstrates the catalog-routing boundary only.

## Real client wiring

A real MCP client can use the same pattern:

1. discover tools from one or more MCP servers;
2. collect the returned tool descriptors;
3. call `route_mcp_tools(user_text, tools)`;
4. expose only the returned descriptors to the model;
5. execute any chosen tool through the normal MCP client path.

The selected descriptors are returned unchanged, so the router does not rewrite their names, descriptions, or input schemas.

## Provenance

For production use, pair this pattern with the routing-provenance design tracked in [Issue #22](https://github.com/sauravsingla/agentweave/issues/22): record the source catalog identity, routing policy/version/configuration, selected model-visible tool set, resulting tool call, and execution result.

The goal is to make it possible to distinguish between a tool that was available but not chosen by the model and a tool that was filtered out before inference.

## Evidence boundary

This example is an ecosystem integration pattern, not a benchmark result. It does not imply official MCP endorsement or any change to the MCP protocol.
