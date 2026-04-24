# MCP Servers and Agent-to-Agent (A2A)

## MCP (Model Context Protocol)

MCP servers expose tools to agents. AgentBreeder has a built-in MCP registry and can auto-discover running MCP servers.

### Quickstart MCP servers

The quickstart stack starts two MCP servers:

| Server | Port | Tools it provides |
|--------|------|-------------------|
| mcp-filesystem | 3100 | read_file, write_file, list_directory, create_directory |
| mcp-memory | 3101 | store_memory, retrieve_memory, list_memories, delete_memory |

### Registering an MCP server

```bash
# Via CLI
agentbreeder scan                   # auto-discovers running MCP servers
agentbreeder provider add ollama    # add providers too

# Via agent.yaml
tools:
  - ref: tools/mcp-filesystem       # reference by registry name
  - name: my-custom-mcp
    type: mcp
    command: npx my-mcp-server
    transport: stdio
```

### Using MCP tools in the search-agent

```bash
agentbreeder chat search-agent
# Ask: "List files in the workspace"
# Ask: "Remember that the project deadline is next Friday"
# Ask: "What did I ask you to remember?"
```

### Packaging your own MCP server

```yaml
# agent.yaml
tools:
  - name: my-mcp
    type: mcp
    command: python server.py
    transport: stdio
    args: [--port, "3200"]
```

The deployer automatically packages the MCP server as a sidecar container injected alongside the agent.

## Agent-to-Agent (A2A) Communication

A2A lets agents call each other over a JSON-RPC protocol. This enables hierarchical multi-agent systems.

### How A2A works

1. Agent A defines an A2A tool pointing to Agent B
2. When the LLM calls that tool, the A2A client sends a JSON-RPC request to Agent B's endpoint
3. Agent B processes the message and returns a response
4. Agent A incorporates the response in its context

### The a2a-orchestrator example

```bash
agentbreeder chat a2a-orchestrator
# Ask: "What is the agent.yaml format?"
#   → Routes to rag-agent (knowledge base question)
# Ask: "Which agents use Neo4j?"
#   → Routes to graph-agent (relationship question)
# Ask: "Find the latest files in the workspace"
#   → Routes to search-agent (filesystem question)
```

### Defining A2A tools in agent.yaml

```yaml
tools:
  - name: call_specialist
    type: a2a
    description: "Call the specialist agent for domain questions"
    agent: specialist-agent          # registered agent name
    protocol: a2a
```

### A2A endpoints

The A2A API is available at `/api/v1/a2a/`:
- `GET /api/v1/a2a/agents` — list A2A-enabled agents
- `POST /api/v1/a2a/agents/{name}/message` — send a message
- `GET /api/v1/a2a/agents/{name}/card` — get agent capabilities card

### Multi-level orchestration

You can build hierarchies:
- Orchestrator → Department agents → Specialist agents
- Each level is a separate agent.yaml
- A2A handles the routing automatically
