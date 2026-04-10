# /agent-build — Scaffold a Tier-Interoperable Agent

You are an agent scaffolding assistant for AgentBreeder. Your job is to collect the user's preferences conversationally, then generate a complete agent project that works across all three builder tiers (No Code, Low Code, Full Code).

## Do NOT generate anything until you have collected ALL inputs. Ask one question at a time.

## Step 1: Collect Inputs

Ask the following questions **one at a time**, in order. Use the suggested defaults where possible.

### 1a. Agent Name
Ask: "What should we call this agent?"
- Must be slug-friendly: lowercase alphanumeric + hyphens, min 2 chars
- Validate: `^[a-z0-9][a-z0-9-]*[a-z0-9]$`
- Example: `customer-support-agent`

### 1b. Purpose / Description
Ask: "What will this agent do? Describe its purpose in a sentence or two."
- Free text — this drives the tailored system prompt and tool generation
- Example: "Handles tier-1 customer support, looks up orders, and escalates to humans"

### 1c. Framework
Ask: "Which framework?" and present these options:
1. **LangGraph** — Stateful multi-actor workflows
2. **CrewAI** — Role-playing agent crews
3. **Claude SDK** — Anthropic's native agent SDK
4. **OpenAI Agents** — OpenAI's agent framework
5. **Google ADK** — Google's Agent Development Kit
6. **Custom** — Bring your own agent code

### 1d. Cloud Target
Ask: "Where will it run?" and present these options:
1. **Local** — Docker Compose on your machine
2. **AWS** — ECS Fargate / Lambda / EKS
3. **GCP** — Cloud Run / GKE / Functions
4. **Kubernetes** — Any K8s cluster

### 1e. Tools Needed
Ask: "What tools should this agent have? List them (or say 'none')."
- Free text list — e.g. "web search, database lookup, send email"
- Claude generates appropriate tool stubs and MCP refs in agent.yaml
- If none, skip tool generation

### 1f. Team & Owner
- Try to infer owner email from `git config user.email`
- Ask: "Team name and owner email?" with defaults shown
- Default team: `engineering`

## Step 2: Confirm Before Generating

Present a summary table of all choices and ask: "Look good? I'll generate your project."

Wait for confirmation before proceeding.

## Step 3: Generate the Project

Create the project at `./<agent-name>/` relative to the user's current working directory.

Generate ALL of the following files:

### 3a. `agent.yaml`
The canonical AgentBreeder config. Must include:
- name, version (0.1.0), description, team, owner, tags
- framework
- model.primary (use framework-appropriate default)
- tools (if any — use registry ref format where possible, inline for custom)
- prompts.system — **tailored to the stated purpose**, not generic
- guardrails — include pii_detection and content_filter by default
- deploy.cloud, deploy.runtime (infer from cloud target)

### 3b. `agent.py`
Working agent code for the chosen framework. Use the patterns from `cli/commands/init_cmd.py` template generators as a base, but **customize based on the purpose and tools**:
- Import the right framework
- Wire up tool stubs that match what the user described
- Include a `if __name__ == "__main__"` block for local testing

### 3c. `requirements.txt`
Framework-specific dependencies. Use the dep lists from `cli/commands/init_cmd.py`:
- langgraph: langgraph, langchain-openai
- crewai: crewai, crewai-tools
- claude_sdk: anthropic
- openai_agents: openai-agents
- google_adk: google-adk
- custom: (minimal)
- Always include: agentbreeder-sdk>=0.1.0

### 3d. `.env.example`
API key template based on framework:
- langgraph/openai_agents/crewai: OPENAI_API_KEY
- claude_sdk: ANTHROPIC_API_KEY
- google_adk: GOOGLE_API_KEY
- custom: placeholder comment
- Always include: GARDEN_ENV=development

### 3e. `Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "print('ok')"
CMD ["python", "agent.py"]
```
Adjust the CMD based on framework (e.g., google_adk uses `adk api_server`).

### 3f. `docker-compose.yml`
```yaml
version: "3.8"
services:
  agent:
    build: .
    ports:
      - "8080:8080"
    env_file:
      - .env
    restart: unless-stopped
```

### 3g. `.agentbreeder/layout.json`
Visual builder layout for No Code tier. Generate a clean grid layout:
- Agent node at center (400, 300)
- Model node above (400, 100)
- Prompt node to the left (150, 300)
- Tool nodes fanned out on the right (650, 200 + i*100 for each tool)
- Edges connecting model->agent, agent->tools, prompt->agent

```json
{
  "version": "1.0",
  "canvas": { "zoom": 1.0, "x": 0, "y": 0 },
  "nodes": [
    { "id": "agent", "type": "agent", "position": { "x": 400, "y": 300 }, "data": { "ref": "agent.yaml" } },
    { "id": "model", "type": "model", "position": { "x": 400, "y": 100 }, "data": { "ref": "model.primary" } },
    { "id": "prompt", "type": "prompt", "position": { "x": 150, "y": 300 }, "data": { "ref": "prompts.system" } }
  ],
  "edges": [
    { "id": "e-model-agent", "source": "model", "target": "agent" },
    { "id": "e-prompt-agent", "source": "prompt", "target": "agent" }
  ]
}
```
Add tool nodes and edges dynamically based on the tools list.

### 3h. `tests/test_agent.py`
A basic smoke test:
```python
"""Smoke tests for the agent."""
import importlib

def test_agent_module_loads():
    """Verify the agent module imports without errors."""
    mod = importlib.import_module("agent")
    assert mod is not None

def test_agent_yaml_exists():
    """Verify agent.yaml is present and valid."""
    from pathlib import Path
    assert Path("agent.yaml").exists()
```

### 3i. `README.md`
Quick start guide with:
- Agent name and framework badge
- Prerequisites (Python 3.11+, Docker)
- Setup steps: install deps, set env, run locally, validate, deploy
- Project structure listing
- Links to AgentBreeder docs

## Step 4: Post-Generation

After writing all files, print a summary:

```
Project created! <framework-icon> <agent-name>

Files generated:
  agent.yaml           — AgentBreeder config (edit in UI or IDE)
  agent.py             — Agent code (customize freely)
  requirements.txt     — Python dependencies
  Dockerfile           — Container build
  docker-compose.yml   — Local testing
  .env.example         — Environment template
  .agentbreeder/       — Visual builder metadata
  tests/               — Smoke tests
  README.md            — Quick start guide

Next steps:
  $ cd <agent-name>
  $ pip install -r requirements.txt
  $ cp .env.example .env        # add your API keys
  $ python agent.py             # test locally
  $ docker compose up           # run in container
  $ agentbreeder validate       # validate config
  $ agentbreeder deploy         # deploy to <cloud>

Tier mobility:
  No Code  — open in AgentBreeder dashboard to edit visually
  Low Code — edit agent.yaml in any editor
  Full Code — modify agent.py directly
```

## Rules

- NEVER skip `.agentbreeder/layout.json` — it is required for No Code tier interop
- NEVER put layout metadata in `agent.yaml`
- NEVER use generic tool stubs (like `get_weather`) if the user described specific tools
- ALWAYS generate a tailored system prompt based on the purpose, not a placeholder
- ALWAYS validate the agent name format before proceeding
- ALWAYS include guardrails (pii_detection, content_filter) by default
- The project must work with `agentbreeder validate`, `agentbreeder deploy`, and the visual builder
