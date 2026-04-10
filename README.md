# AgentBreeder

**Define Once. Deploy Anywhere. Govern Automatically.**

[![CI](https://github.com/open-agent-garden/agentbreeder/actions/workflows/ci.yml/badge.svg)](https://github.com/open-agent-garden/agentbreeder/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/open-agent-garden/agentbreeder/graph/badge.svg)](https://codecov.io/gh/open-agent-garden/agentbreeder)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

AgentBreeder is an open-source platform for deploying, governing, and operating enterprise AI agents. Write one `agent.yaml`, run `agentbreeder deploy`, and your agent is live — with RBAC, cost tracking, audit trail, and org-wide discoverability automatic.

---

## The Problem

- Teams deploy agents with no governance — no RBAC, no audit trail, no cost attribution
- Nobody knows what agents exist across the org or what they cost
- Every framework (LangGraph, OpenAI Agents, etc.) has its own deploy story
- Governance is always bolted on after the fact — or never at all

## How It Works

Write one file. Run one command. Get a governed, observable, discoverable agent.

```yaml
# agent.yaml
name: customer-support-agent
version: 1.0.0
team: customer-success
owner: alice@company.com

framework: langgraph

model:
  primary: claude-sonnet-4
  fallback: gpt-4o

tools:
  - ref: tools/zendesk-mcp
  - ref: tools/order-lookup

deploy:
  cloud: local          # or: gcp (Cloud Run)
  scaling:
    min: 1
    max: 10
```

```bash
agentbreeder deploy ./agent.yaml
# → RBAC validated
# → container built
# → agent deployed
# → registered in org registry
# → endpoint returned
```

Governance is not configuration — it is a structural side effect of the deploy pipeline. Every deploy validates RBAC, writes an audit entry, registers the agent, and attributes cost to the deploying team. There is no way to skip it.

---

## Three Ways to Build

All three tiers compile to the same internal format and run through the same deploy pipeline.

| Tier | Who | How |
|------|-----|-----|
| **No Code** | PMs, analysts, citizen builders | Visual drag-and-drop builder — pick model, tools, prompt from the registry; wire agents together on a canvas |
| **Low Code** | ML engineers, DevOps | Write `agent.yaml` / `orchestration.yaml` in any IDE |
| **Full Code** | Senior engineers, researchers | Python/TypeScript SDK with full programmatic control |

**Tier mobility**: start No Code, view the generated YAML, eject to Full Code with `agentbreeder eject`. No lock-in at any level.

---

## What's Implemented

### Frameworks

| Framework | Status |
|-----------|--------|
| LangGraph | ✅ `engine/runtimes/langgraph.py` |
| OpenAI Agents SDK | ✅ `engine/runtimes/openai_agents.py` |
| CrewAI | 🔲 Planned |
| Claude SDK (Anthropic) | 🔲 Planned |
| Google ADK | 🔲 Planned |

### Cloud Targets

| Target | Status |
|--------|--------|
| Local (Docker Compose) | ✅ `engine/deployers/docker_compose.py` |
| GCP Cloud Run | ✅ `engine/deployers/gcp_cloudrun.py` |
| AWS ECS Fargate | 🔲 Planned |
| Kubernetes | 🔲 Planned |

### LLM Providers

| Provider | Status |
|----------|--------|
| Anthropic (Claude) | ✅ `engine/providers/anthropic_provider.py` |
| OpenAI | ✅ `engine/providers/openai_provider.py` |
| Google (Gemini) | ✅ `engine/providers/google_provider.py` |
| Ollama (local) | ✅ `engine/providers/ollama_provider.py` |
| LiteLLM gateway | ✅ `connectors/litellm/` |
| OpenRouter | ✅ `connectors/openrouter/` |
| Fallback chains | ✅ `engine/providers/registry.py` |

### Secrets Backends

| Backend | Status |
|---------|--------|
| Environment variables | ✅ `engine/secrets/env_backend.py` |
| AWS Secrets Manager | ✅ `engine/secrets/aws_backend.py` |
| GCP Secret Manager | ✅ `engine/secrets/gcp_backend.py` |
| HashiCorp Vault | ✅ `engine/secrets/vault_backend.py` |

### Platform Features

| Feature | Status |
|---------|--------|
| Org-wide agent registry | ✅ |
| Visual agent builder (ReactFlow canvas) | ✅ |
| Multi-agent orchestration (6 strategies) | ✅ |
| Visual orchestration canvas | ✅ |
| Orchestration YAML (`orchestration.yaml`) | ✅ |
| Full Code Orchestration SDK (Python + TS) | ✅ |
| A2A (Agent-to-Agent) protocol | ✅ |
| MCP server hub + sidecar injection | ✅ |
| Agent evaluation framework | ✅ |
| Cost tracking (per team / agent / model) | ✅ |
| RBAC + Teams | ✅ |
| Audit trail | ✅ |
| Distributed tracing (OpenTelemetry) | ✅ |
| AgentOps fleet dashboard | ✅ |
| Community marketplace + templates | ✅ |
| Git workflow (PR create, review, publish) | ✅ |
| Prompt builder + test panel | ✅ |
| RAG index builder | ✅ |
| Memory configuration | ✅ |
| Tool sandbox execution | ✅ |
| Playground (interactive chat) | ✅ |
| API versioning (v1 stable, v2 preview) | ✅ |
| Python SDK | ✅ `sdk/python/` |
| TypeScript SDK | ✅ |
| `agentbreeder eject` (tier mobility) | ✅ |
| SSO / SAML | 🔲 Planned |

---

## Orchestration

Six strategies, all implemented. Define in YAML or the visual canvas — both compile to the same pipeline.

```yaml
# orchestration.yaml
name: support-pipeline
version: "1.0.0"
team: customer-success
strategy: router          # router | sequential | parallel | hierarchical | supervisor | fan_out_fan_in

agents:
  triage:
    ref: agents/triage-agent
    routes:
      - condition: billing
        target: billing
      - condition: default
        target: general
  billing:
    ref: agents/billing-agent
    fallback: general
  general:
    ref: agents/general-agent

shared_state:
  type: session_context
  backend: redis

deploy:
  target: local
```

Or programmatically:

```python
from agenthub import Orchestration

pipeline = (
    Orchestration("support-pipeline", strategy="router", team="eng")
    .add_agent("triage",  ref="agents/triage-agent")
    .add_agent("billing", ref="agents/billing-agent")
    .add_agent("general", ref="agents/general-agent")
    .with_route("triage", condition="billing", target="billing")
    .with_route("triage", condition="default", target="general")
    .with_shared_state(state_type="session_context", backend="redis")
)
pipeline.deploy()
```

---

## Install

### PyPI (recommended)

```bash
# Full CLI + API server
pip install agentbreeder

# Lightweight SDK only
pip install agentbreeder-sdk
```

### Homebrew (macOS / Linux)

```bash
brew tap open-agent-garden/agentbreeder
brew install agentbreeder
```

### Docker

```bash
# API server
docker pull agentbreeder/api
docker run -p 8000:8000 agentbreeder/api

# Dashboard
docker pull agentbreeder/dashboard
docker run -p 80:80 agentbreeder/dashboard

# CLI (for CI/CD pipelines)
docker pull agentbreeder/cli
docker run agentbreeder/cli deploy agent.yaml --target gcp
```

---

## Quick Start

**Prerequisites:** Python 3.11+, Docker, Git

```bash
git clone https://github.com/open-agent-garden/agentbreeder.git
cd agentbreeder

python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# Start postgres + redis + API + dashboard
docker compose -f deploy/docker-compose.yml up -d

# Create and deploy your first agent
agentbreeder init
agentbreeder deploy --target local
```

Dashboard: `http://localhost:3001` · API: `http://localhost:8000` · Docs: `http://localhost:8000/docs`

See [docs/quickstart.md](docs/quickstart.md) for the full guide.

---

## CLI

```bash
agentbreeder init              # Scaffold a new agent project (interactive wizard)
agentbreeder validate          # Validate agent.yaml without deploying
agentbreeder deploy            # Deploy an agent
agentbreeder up                # Start the full local platform stack
agentbreeder down              # Stop the local platform stack
agentbreeder status            # Show deploy status
agentbreeder logs <name>       # Tail agent logs
agentbreeder list              # List agents / tools / models / prompts
agentbreeder describe <name>   # Show detail for a registry entity
agentbreeder search <query>    # Search across the registry
agentbreeder chat <name>       # Interactive chat with a deployed agent
agentbreeder eval              # Run evaluation against golden dataset
agentbreeder eject             # Eject from YAML to Full Code SDK
agentbreeder submit            # Submit a resource for review (creates PR)
agentbreeder review            # Review / approve / reject a PR
agentbreeder publish           # Merge approved PR and publish to registry
agentbreeder provider          # Manage LLM provider connections
agentbreeder secret            # Manage secrets across backends
agentbreeder scan              # Discover MCP servers and LiteLLM models
agentbreeder template          # Manage agent templates
agentbreeder orchestration     # Manage multi-agent orchestrations
agentbreeder teardown          # Remove a deployed agent
```

See [docs/cli-reference.md](docs/cli-reference.md) for full usage and flags.

---

## Architecture

```
Developer                    AgentBreeder Platform                  Cloud
agent.yaml  ──▶  [ CLI ]  ──▶  [ API Server ]  ──▶  [ Engine ]  ──▶  [ GCP / Local ]
                                     │                   │
                                     ▼                   ▼
                               [ PostgreSQL ]     [ Container Build ]
                                 (Registry)              │
                                     │                   ▼
                                  [ Redis ]        [ Agent + MCP Sidecar ]
                                  (Queue)
```

**Deploy pipeline** — all 8 steps are atomic. If any fails, the entire deploy rolls back:

1. Parse & validate YAML
2. RBAC check
3. Dependency resolution (fetch tools, prompts, models from registry)
4. Container build (framework-specific Dockerfile)
5. Infrastructure provision
6. Deploy & health check
7. Auto-register in org registry
8. Return endpoint URL

---

## Project Structure

```
agentbreeder/
├── api/                # FastAPI backend — 25 route modules, services, models
├── cli/                # CLI — 24 commands (Typer + Rich)
├── engine/
│   ├── config_parser.py       # YAML parsing + validation
│   ├── builder.py             # 8-step deploy pipeline
│   ├── orchestrator.py        # Multi-agent orchestration engine
│   ├── providers/             # LLM provider abstraction (Anthropic, OpenAI, Google, Ollama)
│   ├── runtimes/              # Framework builders (LangGraph, OpenAI Agents)
│   ├── deployers/             # Cloud deployers (Docker Compose, GCP Cloud Run)
│   ├── secrets/               # Secrets backends (env, AWS, GCP, Vault)
│   └── a2a/                   # Agent-to-Agent protocol
├── registry/           # Catalog services — agents, tools, models, prompts, templates
├── sdk/python/         # Python SDK (agenthub package)
├── connectors/         # LiteLLM, OpenRouter, MCP scanner
├── dashboard/          # React + TypeScript + Tailwind (36k LOC)
├── tests/              # 73 unit files + Playwright E2E
└── examples/           # Working examples per framework + orchestration strategies
```

---

## Documentation

| Doc | Description |
|-----|-------------|
| [Quickstart](docs/quickstart.md) | Local setup in under 10 minutes |
| [CLI Reference](docs/cli-reference.md) | All commands with flags and examples |
| [agent.yaml Reference](docs/agent-yaml.md) | Full configuration field reference |
| [orchestration.yaml Reference](docs/orchestration-yaml.md) | Multi-agent pipeline configuration |
| [Orchestration SDK](docs/orchestration-sdk.md) | Python/TypeScript SDK for complex workflows |
| [API Stability](docs/api-stability.md) | Versioning and deprecation policy |
| [Local Development](docs/local-development.md) | Contributor setup guide |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical deep-dive |
| [ROADMAP.md](ROADMAP.md) | Release plan and milestone status |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to add deployers, runtimes, connectors |

---

## Contributing

High-impact areas:
- **AWS ECS deployer** — `engine/deployers/aws_ecs.py` — most requested cloud target
- **Framework runtimes** — CrewAI, Claude SDK, Google ADK in `engine/runtimes/`
- **Agent templates** — add to `templates/` and `examples/`
- **Connectors** — Datadog, Grafana, and other observability integrations

See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

---

## Community

- [GitHub Issues](https://github.com/open-agent-garden/agentbreeder/issues) — bugs and feature requests
- [GitHub Discussions](https://github.com/open-agent-garden/agentbreeder/discussions) — questions and show & tell

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
