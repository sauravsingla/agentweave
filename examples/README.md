# Examples

Run commands from the repository root. Install the package and the optional
dependency group shown for each example first. Unless noted, examples use local
or scripted components and need no model API key.

| File | What it demonstrates | Install | Run | Network or credentials? |
| --- | --- | --- | --- | --- |
| [`demo.py`](demo.py) | In-memory A2A agent marketplace and local routing | `python -m pip install -e .` | `python examples/demo.py` | No network or credentials. |
| [`byom_agentweave.py`](byom_agentweave.py) | Provider-neutral model callback and tool routing | `python -m pip install -e .` | `python examples/byom_agentweave.py` | No network or credentials; uses a local callback that can be replaced with a provider SDK. |
| [`local_runtime.py`](local_runtime.py) | Route a task to local tools and execute one without a model service | `python -m pip install -e '.[dev]'` | `python examples/local_runtime.py` | No network or credentials; uses a scripted model. |
| [`mcp_tool_routing.py`](mcp_tool_routing.py) | Discover tools from an MCP server and route a query | `python -m pip install -e '.[mcp]'` | `python examples/mcp_tool_routing.py --url http://localhost:8000/mcp --query 'Search the codebase'` | Requires a reachable MCP server at `--url`; no model API credentials. |
| [`multi_mcp_collision.py`](multi_mcp_collision.py) | Run two in-process MCP servers with the same tool name and route to both | `python -m pip install -e '.[mcp]'` | `python examples/multi_mcp_collision.py` | No network or credentials; uses in-process servers and a scripted model. |
| [`langgraph_agentweave.py`](langgraph_agentweave.py) | Use AgentWeave routing as a node in a LangGraph workflow | `python -m pip install -e '.[langgraph]'` | `python examples/langgraph_agentweave.py` | No network or credentials; uses a local stub model. |
| [`autogen_agentweave.py`](autogen_agentweave.py) | Select AutoGen participants using AgentWeave, then run a local team | `python -m pip install -e '.[autogen]'` | `python examples/autogen_agentweave.py` | No network or credentials; uses local demo agents and model. |
| [`plugin_example.py`](plugin_example.py) | Minimal plugin implementing the AgentWeave plugin interface | `python -m pip install -e .` | `python examples/plugin_example.py` | No network or credentials. |

For a provider-neutral runtime quickstart, see
[`docs/QUICKSTART_0_7.md`](../docs/QUICKSTART_0_7.md). For MCP integration
details, see [`docs/MCP_INTEGRATION.md`](../docs/MCP_INTEGRATION.md). Optional
dependency groups are defined in [`pyproject.toml`](../pyproject.toml).
