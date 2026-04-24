# What is AgentBreeder?

AgentBreeder is an open-source platform for building, deploying, and governing enterprise AI agents.

**Core tagline:** Define Once. Deploy Anywhere. Govern Automatically.

## The one-sentence pitch

A developer writes one `agent.yaml` file, runs `agentbreeder deploy`, and their agent is live on AWS or GCP — with RBAC, cost tracking, audit trail, and org-wide discoverability automatic and zero extra work.

## What makes it unique

- **Framework-agnostic** — LangGraph, CrewAI, Claude SDK, OpenAI Agents, Google ADK, Custom
- **Multi-cloud first** — AWS ECS Fargate, GCP Cloud Run, Azure Container Apps, Kubernetes, local Docker
- **Governance is a side effect** — not extra configuration
- **Shared org-wide registry** — agents, prompts, tools, MCP servers, models, knowledge bases
- **Three builder tiers** — No Code (drag-and-drop UI), Low Code (YAML), Full Code (Python/TS SDK)
- **Tier mobility** — start No Code, eject to YAML, eject to Full Code — no vendor lock-in

## Who is it for?

| Role | How they use AgentBreeder |
|------|--------------------------|
| ML Engineer | Write agent.yaml, `agentbreeder deploy`, done |
| DevOps | Manage providers, secrets, cloud targets via CLI |
| PM / Analyst | Build agents visually in the dashboard with no code |
| Security team | Audit logs, RBAC, cost attribution are automatic |
| Platform team | Self-host the registry, govern all org agents |

## Key concepts

- **agent.yaml** — the single config file that defines an agent (model, tools, prompts, deployment target)
- **Registry** — org-wide catalog of agents, tools, prompts, models, MCP servers
- **Deploy pipeline** — Parse → RBAC check → Dependency resolution → Build → Deploy → Register
- **Governance** — RBAC, cost attribution, audit logs — happen automatically on every deploy
