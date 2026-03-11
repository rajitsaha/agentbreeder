# Udemy Agent Platform (UAP) — Pitch Document

**Date:** March 2026
**Author:** Agent Infrastructure Team
**Status:** Active Development, Production Workloads Running

---

## 1. Executive Summary

AI agents are no longer experimental. They are becoming the primary interface through which
enterprises automate complex workflows — customer support triage, content quality assessment,
data pipeline debugging, personalized learning paths. At Udemy, multiple teams have already
built or are actively building AI agents. The problem is that each team is rebuilding the
same infrastructure from scratch: framework selection, tool integration, memory management,
deployment pipelines, cost tracking, and governance. This duplication is expensive, slow,
and produces agents that are difficult to operate in production.

The Udemy Agent Platform (UAP) eliminates this redundancy. It is a single platform where
any Udemy team can build, test, deploy, and operate AI agents — regardless of their
technical sophistication. A product manager can drag and drop an agent in the visual
builder. A backend engineer can write a YAML config and a prompt file. A machine learning
engineer can write custom code in any framework they choose. All three approaches produce
agents with the same HTTP API, the same deployment model, and the same operational
guarantees: cost tracking, guardrails, rate limiting, audit logs, and governance approvals.

Today, UAP runs 30 agents in production and development across three teams. It provides
83+ pre-built tools, 13 MCP servers, 16 SDK templates, and deploys to 10 infrastructure
targets. The platform is not a proposal — it is running code with 2,500+ tests at 80%+
coverage. This document makes the case for continued investment and broader adoption.

---

## 2. Vision

**Every AI agent at Udemy ships in hours, not months — with production-grade
operations from day one.**

---

## 3. Mission

UAP provides Udemy engineering teams with a unified platform to author, test, deploy,
monitor, and govern AI agents. It abstracts away framework choices, infrastructure
complexity, and operational overhead so that teams can focus on the domain logic that
makes their agents valuable.

---

## 4. The Problem

### 4.1 The Agent Infrastructure Tax

Building a useful AI agent requires solving a stack of infrastructure problems before
writing a single line of domain logic:

| Layer | What You Need | Typical Effort |
|-------|--------------|----------------|
| **Framework** | Choose LangChain, Mastra, CrewAI, Google ADK, etc. | 1-2 weeks evaluation |
| **Tool Integration** | Connect to Zendesk, Databricks, Jira, Airflow, etc. | 2-4 weeks per tool |
| **Memory** | Conversation history, semantic recall, entity tracking | 1-2 weeks |
| **Deployment** | Dockerize, configure Kubernetes, set up CI/CD | 1-2 weeks |
| **Monitoring** | Health checks, metrics, distributed tracing | 1 week |
| **Cost Tracking** | Token counting, budget alerts, forecasting | 1 week |
| **Guardrails** | Content policy, PII redaction, output validation | 1 week |
| **Governance** | Approval workflows, audit logs, RBAC | 1-2 weeks |

That is 8-16 weeks of infrastructure work — per team, per agent. At Udemy, three teams
have independently built this stack. That is 24-48 engineer-weeks of duplicated effort,
producing three incompatible implementations that cannot share tools, learnings, or
operational patterns.

### 4.2 Framework Fragmentation

The AI agent framework landscape is fragmented and evolving rapidly:

```
2024                    2025                    2026
 |                       |                       |
 LangChain 0.1           LangGraph 0.2           LangGraph 0.3
 AutoGen                  CrewAI                  Google ADK
 Semantic Kernel          Mastra                  Claude SDK
                          OpenAI Agents SDK       Strands
                          Pydantic AI             Koog (Kotlin)
```

Choosing a single framework creates lock-in. When a team builds on LangChain, they
cannot easily adopt innovations from Mastra (native TypeScript, streaming-first) or
Google ADK (multi-modal, grounding). When a framework falls behind or changes its API
(as LangChain did between v0.1 and v0.2), the migration cost falls entirely on the
application team.

### 4.3 The "Last Mile" Gap

Building a working agent prototype is straightforward. Getting that agent to production
is where projects stall or fail:

```
Prototype                              Production
 (works on laptop)                      (runs reliably at scale)
        |                                      |
        |  ---- The Last Mile Gap ----         |
        |                                      |
        |  - Authentication & RBAC             |
        |  - Rate limiting per tenant          |
        |  - Graceful degradation              |
        |  - Cost budgets & alerts             |
        |  - Human-in-the-loop approval        |
        |  - Audit logging                     |
        |  - Canary deployments                |
        |  - Multi-region failover             |
        |  - Model fallback chains             |
        |  - Input/output guardrails           |
        |                                      |
```

Most agent frameworks focus on the prototype side. They provide excellent abstractions
for prompt engineering, tool calling, and memory. They provide little or nothing for
operations: cost tracking, governance, guardrails, and deployment automation are left
as exercises for the reader.

### 4.4 Cost Blindness

LLM API costs are opaque and unpredictable. A single agent running Claude Sonnet 4.5
with tool calls can consume $50-200/day depending on traffic patterns and prompt length.
Multiply that by 30 agents and the monthly bill becomes significant. Without per-agent,
per-team, per-model cost attribution — built into the platform — teams discover cost
problems only when the invoice arrives.

---

## 5. The Solution — Udemy Agent Platform

UAP is a unified platform with four layers:

```
+------------------------------------------------------------------+
|                         UI (React SPA)                           |
|  Agent Builder (4 modes) | Dashboards | Marketplace | Monitoring |
+------------------------------------------------------------------+
        |                    |                    |
        v                    v                    v
+------------------------------------------------------------------+
|                  Unified Backend (:8080)                          |
|                                                                  |
|  Builders          Platform           Runtime                    |
|  --------          --------           -------                    |
|  Agent Builder      Registry          Sandbox (Docker)           |
|  Prompt Builder     Auth (OAuth/JWT)  A2A Server (JSON-RPC)      |
|  Tool Builder       Model Gateway     MCP Server Registry        |
|  RAG Builder        Governance        Deployer (10 targets)      |
|  Memory Builder     Monitoring                                   |
|  Marketplace        Cost Tracker                                 |
|                     Inference Capture                             |
+------------------------------------------------------------------+
        |                    |                    |
        v                    v                    v
+------------------------------------------------------------------+
|                   Agent Runtimes                                 |
|                                                                  |
|  TypeScript Runtime     Python Runtime      Kotlin Runtime       |
|  (Mastra + Vercel AI)   (FastAPI +           (Ktor + Koog)       |
|                          LangChain)                              |
|                                                                  |
|  All read the same agent.yaml + prompt.md                        |
+------------------------------------------------------------------+
        |                    |                    |
        v                    v                    v
+------------------------------------------------------------------+
|                   Infrastructure                                 |
|                                                                  |
|  13 MCP Servers    PostgreSQL + pgvector    Redis                |
|  (ports 9100-9112) Prisma ORM (27 models)  Rate limit + cache   |
|                                                                  |
|  Deployment Targets: EKS, GKE, Fargate, Cloud Run, Azure,       |
|  OKE, Bedrock, Databricks Apps, Docker, Kubernetes               |
+------------------------------------------------------------------+
```

### Key Capabilities

| Capability | Description |
|-----------|-------------|
| **Author** | 3-tier model: visual, YAML, or full code. 16 SDK templates. |
| **Test** | Sandbox execution, prompt testing, A2A simulation. |
| **Deploy** | One-click to 10 targets. Helm chart, ArgoCD, Terraform included. |
| **Operate** | Health checks, distributed tracing, alerting, auto-scaling. |
| **Govern** | Approval workflows, policy enforcement, audit logs, RBAC. |
| **Track** | Per-agent cost attribution, budget alerts, spend forecasting. |
| **Guard** | Input/output content policies, PII redaction, model fallback. |
| **Share** | Marketplace for agents, tools, prompts, RAG collections. |

---

## 6. Three-Tier Authoring Model

UAP supports three tiers of agent authoring. All three produce agents with identical
HTTP APIs (`/invocations`, `/invocations/stream`) and identical deployment models
(Docker container served by a shared runtime).

### Tier 1: No-Code (Visual Builder)

For product managers, analysts, and rapid prototyping.

```
+-------+     +-------+     +----------+     +--------+
| Model |---->| Agent |---->| Tool:    |     | Memory |
| GPT-4 |     | Root  |     | Zendesk  |     | Buffer |
+-------+     +-------+     +----------+     +--------+
                  |
                  +--------->+----------+
                             | Guardrail|
                             | PII Check|
                             +----------+
```

Drag nodes onto a canvas. Connect them. The visual graph compiles to `agent.yaml`
behind the scenes. No code, no YAML editing required.

### Tier 2: Low-Code (YAML + Prompt) — Default

For engineers who want control without boilerplate. This is the recommended tier for
most agents.

**agent.yaml:**
```yaml
agent:
  name: support-agent
  version: "1.0.0"
  model:
    provider: anthropic
    name: claude-sonnet-4-5
    temperature: 0.7
  system_prompt_ref: prompt.md
  tools:
    - uap_toolkit.zendesk.search_help_articles
  memory:
    type: buffer_window
    max_messages: 20
```

**prompt.md:**
```markdown
You are a Udemy support agent. Help users resolve account issues,
course access problems, and billing questions. Always search the
help center before asking the user for more details.
```

Two files. No framework code. The shared runtime reads the YAML, wires the tools,
loads the prompt, and serves the agent over HTTP.

### Tier 3: Full Code (Any Framework)

For ML engineers who need custom tools, complex orchestration, or non-standard
frameworks.

Write a standalone project in any language, using any framework. UAP provides 16 SDK
templates (9 Python, 6 TypeScript, 1 Kotlin) as starting points. Full-code agents
still deploy through the same pipeline and appear in the same registry, monitoring,
and cost tracking dashboards.

### Progressive Complexity

The key insight is that tiers are not silos. An agent can start as a visual prototype
(Tier 1), graduate to YAML when it needs more control (Tier 2), and eventually become
a full-code project if it needs custom orchestration (Tier 3). Each transition
preserves the agent's identity, deployment configuration, and operational history.

---

## 7. What's Built Today

UAP is not a design document. It is running software.

### Platform Numbers

| Metric | Count |
|--------|-------|
| Production agents | 22 |
| Example/demo agents | 8 |
| Pre-built tools | 83+ across 22 modules |
| MCP servers | 13 |
| SDK templates | 16 (9 Python, 6 TypeScript, 1 Kotlin) |
| Supported model providers | 18 |
| Deployment targets | 10 |
| Backend feature modules | 18 (unified single-process) |
| Database models (Prisma) | 27 |
| API route prefixes | 47 |
| Test count | 2,500+ |
| Coverage threshold | 80% (enforced) |
| UI dashboards | 12 |

### Supported Model Providers

| Provider | Models |
|----------|--------|
| Anthropic | Claude Sonnet 4.5, Claude Haiku |
| OpenAI | GPT-4.1, GPT-4o, o3-mini |
| Google | Gemini 2.5 Pro, Gemini 2.5 Flash |
| Databricks | Foundation Model API (Claude, GPT, Llama via serving endpoints) |
| xAI | Grok |
| DeepSeek | DeepSeek-V3, DeepSeek-R1 |
| And others | Groq, Together, Fireworks, Perplexity, Mistral, Cohere, etc. |

### Tool Modules

| Module | Tools | Integration |
|--------|-------|-------------|
| `zendesk` | 1 | Help article search |
| `course_catalog` | 2 | Course discovery |
| `featurestore` | 2 | ML feature queries |
| `learner_state` | 2 | Progress tracking |
| `learner_profile` | 2 | User profiles |
| `goal_elicitation` | 2 | Learning goals |
| `databricks.query` | 2 | SQL execution |
| `databricks.user` | 1 | User info |
| `databricks.lineage` | 2 | Table/column lineage |
| `databricks.job` | 4 | Job management |
| `atlassian` | 4 | Jira + Confluence |
| `airflow.dag` | 9 | DAG operations |
| `cip.content_quality` | 10 | Quality scoring |
| `taxonomy` | 1 | Topic classification |
| `memory` | 3 | Conversation persistence |
| And 7 more modules | 36 | Tutoring, onboarding, S3, etc. |

### Deployment Targets

| Target | Status |
|--------|--------|
| Amazon EKS | Production (Helm + ArgoCD) |
| Google GKE | Production (Helm) |
| AWS Fargate | Supported |
| Google Cloud Run | Supported |
| Azure Container Apps | Supported |
| Oracle OKE | Supported |
| Amazon Bedrock | Supported |
| Databricks Apps | Production |
| Docker Compose | Development |
| Raw Kubernetes | Supported |

---

## 8. Impact and Adoption

### Teams Using UAP

| Team | Agents | Use Cases |
|------|--------|-----------|
| **Content Intelligence** | 5 | Taxonomy classification, quality scoring, content pruning, SKU matching, supply intelligence |
| **Data Platform** | 3 | Support ticket triage, data lineage exploration, infrastructure cost optimization |
| **Learning Experience** | 9 | Course personalization, microlearning (goal elicitation, lesson planning, tutoring, content analysis), educational search |
| **Platform / Infra** | 5 | Streaming demos, supervisor orchestration, A2A protocol examples |

### Workflows Automated

**Content Intelligence Pipeline:**
An untagged course enters the system. The taxonomy agent classifies it against Udemy's
topic hierarchy using vector search over approved topics. The content quality agent
scores it on 8 dimensions (production quality, instructor delivery, content depth,
visual aids, engagement, practical application, course structure, professionalism).
A human reviewer approves or adjusts the classifications. Previously, this workflow
required manual review of thousands of courses per quarter. Now it runs continuously
with human-in-the-loop approval only for edge cases.

**Data Platform Support:**
An engineer asks "why did the user_course_activity pipeline fail last night?" The
dp-support-agent searches Jira for related incidents, queries Airflow for DAG run
status, checks Databricks job logs, and searches Confluence for runbook documentation.
It synthesizes a root-cause summary with remediation steps. Response time dropped from
hours of manual investigation to seconds.

**Microlearning Orchestration:**
A learner opens the Udemy app. The goal elicitation agent identifies what they want to
learn. The planner agent selects relevant course content. The course agent delivers
bite-sized lessons. The tutor agent answers questions in real-time. Four agents
coordinate via A2A protocol, supervised by a lightweight orchestrator. The entire
interaction feels like a single conversation.

---

## 9. Why Now

### The Market Has Shifted

2024 was the year of agent experimentation. 2025-2026 is the year of agent
operationalization. The industry has moved from "can we build an agent?" to "how do we
run 50 agents in production reliably and cost-effectively?"

This shift creates a window of opportunity. Teams that invest in agent infrastructure
now will move faster as the number of agent use cases grows. Teams that do not will
accumulate technical debt with each new ad-hoc agent deployment.

### Framework Convergence on Standards

Two standards have emerged that make a platform approach viable:

1. **MCP (Model Context Protocol):** A standard for connecting LLMs to external tools.
   UAP already runs 13 MCP servers. As more tool providers ship MCP-compatible
   interfaces, the UAP tool library grows without custom integration work.

2. **A2A (Agent-to-Agent Protocol):** A standard for inter-agent communication.
   UAP implements JSON-RPC 2.0 A2A, enabling multi-agent workflows where agents from
   different teams collaborate on complex tasks.

### Udemy's Unique Position

Udemy has domain-specific advantages that generic agent platforms cannot replicate:

- **Content graph:** 200,000+ courses, hierarchical topic taxonomy, quality metadata.
- **Learner data:** Enrollment patterns, progress signals, skill assessments.
- **Operational data:** Databricks pipelines, Airflow DAGs, infrastructure metrics.
- **Pre-built integrations:** Zendesk, Jira, Confluence, Databricks, Airflow — all
  already wired as UAP tools.

A generic platform like AWS Bedrock Agents or Google Vertex AI Agent Builder provides
model hosting and basic tool calling. UAP provides that plus 83 Udemy-specific tools,
30 battle-tested agent configurations, and operational patterns refined through
production usage.

---

## 10. Technical Architecture (High Level)

UAP runs as a single unified Express.js process on port 8080, consolidating what were
originally 18 separate microservices into one deployment unit. This eliminates
inter-service networking complexity and reduces operational overhead.

```
Requests
   |
   v
[Auth Middleware] --> JWT validation, API key check, RBAC
   |
   v
[Rate Limiter] --> 3-tier: global, per-user, per-agent
   |
   v
[Router] --> 47 route prefixes across 18 modules
   |
   +--> /api/v1/registry/*        (agent/tool/prompt/rag CRUD)
   +--> /api/v1/agents/*          (agent builder, filesystem, generation)
   +--> /api/v1/prompts/*         (prompt versioning, testing)
   +--> /api/v1/tools/*           (tool CRUD, sandbox execution)
   +--> /api/v1/rag/*             (vector collections, search)
   +--> /api/v1/memory/*          (conversation history)
   +--> /api/v1/marketplace/*     (browsing, reviews, installs)
   +--> /api/v1/models/*          (multi-provider routing, guardrails)
   +--> /api/v1/governance/*      (approvals, policies, audit)
   +--> /api/v1/monitoring/*      (health, metrics, traces, alerts)
   +--> /api/v1/costs/*           (tracking, budgets, forecasting)
   +--> /api/v1/inference/*       (capture, buffering, S3 export)
   +--> /api/v1/sandbox/*         (Docker code execution)
   +--> /api/v1/a2a/*             (agent-to-agent JSON-RPC 2.0)
   +--> /api/v1/mcp/*             (MCP server management)
   +--> /api/v1/deploy/*          (multi-target deployment)
   |
   v
[Shared Infrastructure]
   PostgreSQL (Prisma, 27 models) + Redis (caching, rate limits)
```

### Shared Runtimes

The three runtimes are the core innovation. Each reads the same `agent.yaml` format
and produces an agent with identical HTTP endpoints:

```
                    agent.yaml + prompt.md
                           |
              +------------+------------+
              |            |            |
              v            v            v
        +---------+  +---------+  +---------+
        |   TS    |  | Python  |  | Kotlin  |
        | Runtime |  | Runtime |  | Runtime |
        | Mastra  |  | FastAPI |  |  Ktor   |
        | Vercel  |  |LangChain|  |  Koog   |
        +---------+  +---------+  +---------+
              |            |            |
              v            v            v
        POST /invocations      (synchronous)
        POST /invocations/stream (SSE streaming)
        GET  /health
        GET  /.well-known/agent.json (A2A discovery)
```

Teams choose a runtime based on their language preference or framework needs. The
platform does not care — all agents look the same to the registry, deployer, monitor,
and cost tracker.

For full architectural details, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 11. Roadmap Preview

The platform is functional today. The roadmap focuses on three themes:

### Theme 1: Evaluation and Quality

Systematic agent evaluation: automated test suites, regression detection, A/B testing
of prompt variants, offline evaluation against golden datasets. The goal is to make
agent quality as measurable and improvable as traditional software quality.

### Theme 2: Multi-Agent Orchestration

Advanced orchestration patterns: hierarchical delegation, parallel fan-out/fan-in,
conditional routing, shared blackboard memory. Building on the A2A foundation to
support workflows where 5-10 agents collaborate on complex tasks.

### Theme 3: Self-Service and Scale

Reduce time-to-first-agent to under 30 minutes for any Udemy engineer. Expand the
tool library to 150+ tools. Add self-service onboarding, documentation, and
interactive tutorials within the platform UI.

For the detailed roadmap, see [`ROADMAP.md`](ROADMAP.md).

---

## 12. Summary

UAP exists because building AI agents should be a product decision, not an
infrastructure project.

The platform is live. Thirty agents are running. Three teams are building on it.
The tool library covers Udemy's core systems. The deployment pipeline supports ten
infrastructure targets. The operational layer — cost tracking, governance, guardrails,
monitoring — is built in from the start, not bolted on as an afterthought.

The ask is straightforward: continued investment in the platform team, broader adoption
across Udemy engineering, and organizational commitment to building agents on shared
infrastructure rather than bespoke implementations.

Every agent built on UAP makes the platform more valuable. Every tool added to the
registry is available to every agent. Every operational pattern refined through
production usage benefits every team. That compounding effect is the core argument
for a platform approach to AI agents.

---

## Appendix: Key Links

| Resource | Location |
|----------|----------|
| Architecture | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| Unified Platform Design | [`docs/UNIFIED_PLATFORM.md`](UNIFIED_PLATFORM.md) |
| API Reference | [`docs/SERVICES.md`](SERVICES.md) |
| Deployment Guide | [`docs/DEPLOYMENT.md`](DEPLOYMENT.md) |
| Development Guide | [`docs/DEVELOPMENT.md`](DEVELOPMENT.md) |
| Database Schema | [`docs/DATABASE.md`](DATABASE.md) |
| Roadmap | [`docs/ROADMAP.md`](ROADMAP.md) |
| Agent Configurations | `agents/` (22 production + 8 examples) |
| Shared Runtimes | `agent-runtime/`, `agent-runtime-python/`, `agent-runtime-kotlin/` |
| Tool Library | `uap-toolkit/src/` (83+ tools, 22 modules) |
| MCP Servers | `mcps/servers/` (13 servers) |
| SDK Templates | `sdks/` (16 templates) |
| UI | `ui/` (React SPA, 12 dashboards) |
