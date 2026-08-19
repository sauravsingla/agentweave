# Bring Your Own Model (BYOM)

AgentWeave is a routing and orchestration layer, not a model. The BYOM path lets an application keep its preferred model provider while AgentWeave reduces the model-visible tool set before inference.

To preserve the repository's frozen research-core integrity checks, BYOM is packaged as the companion `agentweave_byom` module while reusing the normal AgentWeave orchestration components.

```text
user task
   ↓
full tool catalog
   ↓
AgentWeave deterministic pre-inference routing
   ↓
smaller model-visible tool set
   ↓
user-supplied model
   ↓
normal tool/function call handling
```

## Quick start with any SDK

Wrap any synchronous or asynchronous provider SDK with `CallableModelAdapter`:

```python
from agentweave_byom import BYOMAgentWeave, CallableModelAdapter

async def call_my_model(*, messages, tools, **kwargs):
    # Call Anthropic, Gemini, a private gateway, Hugging Face,
    # or another provider here.
    return await my_client.generate(messages=messages, tools=tools, **kwargs)

weave = BYOMAgentWeave(
    model=CallableModelAdapter(call_my_model, name="my-provider/my-model"),
    tools=my_tools,
)

result = await weave.run("Find the latest invoice", max_tools=6)
```

AgentWeave routes first and sends only the selected tool subset to the user model.

## OpenAI-compatible endpoints

For OpenAI-shaped `/chat/completions` APIs, use the built-in adapter:

```python
from agentweave_byom import BYOMAgentWeave, OpenAICompatibleModelAdapter

model = OpenAICompatibleModelAdapter(
    model="my-model",
    base_url="http://localhost:8000/v1",
    api_key=None,
)

weave = BYOMAgentWeave(model=model, tools=my_tools)
result = await weave.run("Summarize the customer account", max_tools=8)
```

This adapter is suitable for compatible hosted gateways and local runtimes such as vLLM, Ollama compatibility mode, or llama.cpp servers when they expose the expected chat-completions interface.

## Provider-neutral contract

A custom model only needs to implement:

```python
await adapter.complete(messages, tools=selected_tools, **model_kwargs)
```

The model can be local or remote. AgentWeave does not require a particular vendor or model family.

## Routing provenance

Every BYOM invocation returns a routing record containing:

- router version;
- source catalog SHA-256 fingerprint;
- source catalog size;
- selected tools;
- filtered tools;
- routing scores;
- configured model-adapter identity.

This makes it possible to distinguish a tool that the model saw but did not call from a tool that AgentWeave filtered out before inference.

## Important research boundary

BYOM is a general product/runtime feature. It does **not** alter historical frozen research evidence. The frozen `agentweave/` core remains unchanged by this feature. Existing BFCL-derived routing-pressure studies remain pinned to their original model, protocol, sample, router configuration, artifacts, and canonical scored runs.

Using another model creates a new runtime configuration; it must not be presented as reproducing a frozen BFCL result unless a new study is explicitly defined and evaluated.
