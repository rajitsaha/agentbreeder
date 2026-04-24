# Supported Frameworks

AgentBreeder is framework-agnostic. The `framework` field in `agent.yaml` selects the runtime.

## LangGraph

Best for: stateful agents, complex workflows, human-in-the-loop, graph-based control flow.

```yaml
framework: langgraph
```

AgentBreeder generates a LangGraph server wrapping your graph. Place your graph definition in `agent.py` with a `graph` variable. The server is auto-generated.

```python
# agent.py
from langgraph.graph import StateGraph, END
from typing import TypedDict

class State(TypedDict):
    messages: list

def my_node(state: State) -> State:
    # your logic
    return state

graph = StateGraph(State)
graph.add_node("my_node", my_node)
graph.set_entry_point("my_node")
graph.add_edge("my_node", END)
graph = graph.compile()
```

## CrewAI

Best for: multi-agent crews with roles, collaborative task execution.

```yaml
framework: crewai
```

Define your crew in `crew.py`. AgentBreeder auto-injects `AGENT_MODEL` and `AGENT_TEMPERATURE` env vars.

## Claude SDK (Anthropic)

Best for: Claude-native agents with adaptive thinking, extended context, prompt caching.

```yaml
framework: claude_sdk
claude_sdk:
  thinking:
    type: adaptive
    effort: high
  prompt_caching: true
```

## OpenAI Agents

Best for: function-calling agents, Assistants API patterns.

```yaml
framework: openai_agents
```

## Google ADK

Best for: Gemini-native agents, Vertex AI integration.

```yaml
framework: google_adk
google_adk:
  session_backend: memory
  memory_service: memory
```

## Custom

Bring your own runtime. Implement the runtime interface and package as a container.

```yaml
framework: custom
```

## How frameworks are abstracted

All frameworks share the same deploy pipeline. Framework-specific logic lives only in `engine/runtimes/`. The pipeline never sees framework names — it calls the runtime interface:

```python
class RuntimeBuilder(ABC):
    def validate(self, agent_dir, config) -> ValidationResult: ...
    def build(self, agent_dir, config) -> ContainerImage: ...
    def get_entrypoint(self, config) -> str: ...
    def get_requirements(self, config) -> list[str]: ...
```
