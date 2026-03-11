# Architecture

Comprehensive architecture reference for the Udemy Agent Platform (UAP).

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture Diagram](#2-system-architecture-diagram)
3. [Unified Backend](#3-unified-backend)
4. [Platform Layer](#4-platform-layer)
5. [Builder Layer](#5-builder-layer)
6. [Runtime Layer](#6-runtime-layer)
7. [Agent Runtime Architecture](#7-agent-runtime-architecture)
8. [Tool Ecosystem](#8-tool-ecosystem)
9. [Data Model](#9-data-model)
10. [Frontend Architecture](#10-frontend-architecture)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Observability](#12-observability)
13. [Security](#13-security)
14. [Background Workers](#14-background-workers)
15. [Data Flow Diagrams](#15-data-flow-diagrams)

---

## 1. Overview

UAP is an enterprise platform for building, testing, deploying, and operating AI agents. It runs as a single unified Express.js process on port 8080, serving 47 API route prefixes across 18 feature modules. Alongside the backend sits a React 19 SPA for the management UI and three shared agent runtimes (TypeScript, Python, Kotlin) that can serve any agent from a declarative YAML configuration.

### Key Numbers

| Dimension | Count |
|-----------|-------|
| Backend feature modules | 18 (7 platform + 6 builder + 4 runtime + 1 shared) |
| API route prefixes | 47 |
| Production agents | 22 |
| Example agents | 8 |
| Agent runtimes | 3 (TypeScript, Python, Kotlin) |
| SDK templates | 16 (9 Python + 6 TypeScript + 1 Kotlin) |
| Toolkit tools | 83+ across 22 modules |
| MCP servers | 13 |
| Prisma models | 27 |
| Prisma enums | 19 |
| Deployment targets | 10 |
| LLM providers | 18 |

### 3-Tier Agent Authoring Model

All agents produce the same HTTP API (`/invocations`, `/invocations/stream`) and follow the same deployment model (Docker container served by a shared runtime or standalone process).

| Tier | Approach | UI Mode | Best For |
|------|----------|---------|----------|
| No-Code | Visual drag-and-drop (ReactFlow) | Visual | Prototyping, non-developers |
| Low-Code | `agent.yaml` + `prompt.md` + shared runtime | YAML + Prompt | Standard agents (default) |
| Full Code | Standalone project (any framework) | IDE | Custom tools, complex orchestration |

---

## 2. System Architecture Diagram

```
                                    CLIENTS
                ┌──────────────────────────────────────────────┐
                │  React SPA (:3000)    CLI     External APIs  │
                └───────────────────────┬──────────────────────┘
                                        │ HTTPS
                ┌───────────────────────▼──────────────────────┐
                │          UNIFIED EXPRESS APP (:8080)          │
                │                                              │
                │  ┌──────────────────────────────────────┐    │
                │  │          Global Middleware             │    │
                │  │  Helmet → CORS → JSON → pino-http     │    │
                │  │  → Auth (JWT) → Rate Limiting         │    │
                │  └──────────────────────────────────────┘    │
                │                                              │
                │  ┌────────────┐ ┌────────────┐ ┌──────────┐ │
                │  │  PLATFORM  │ │  BUILDERS  │ │ RUNTIME  │ │
                │  │  7 modules │ │  6 modules │ │ 4 modules│ │
                │  ├────────────┤ ├────────────┤ ├──────────┤ │
                │  │ Registry   │ │ Agent Bldr │ │ Sandbox  │ │
                │  │ Auth/RBAC  │ │ Prompt Bldr│ │ A2A Srv  │ │
                │  │ Model GW   │ │ Tool Bldr  │ │ MCP Srv  │ │
                │  │ Governance │ │ RAG Bldr   │ │ Deployer │ │
                │  │ Monitoring │ │ Memory Bldr│ └──────────┘ │
                │  │ Cost Track │ │ Marketplace│              │
                │  │ Inf.Capture│ └────────────┘              │
                │  └────────────┘                              │
                └──────┬──────────────┬───────────────┬────────┘
                       │              │               │
           ┌───────────▼──┐  ┌───────▼────┐  ┌───────▼────────┐
           │ PostgreSQL 16 │  │  Redis 7   │  │ Object Storage │
           │  + pgvector   │  │  (ioredis) │  │  (S3 / MinIO)  │
           └──────────────┘  └────────────┘  └────────────────┘

        ┌──────────────────────────────────────────────────────┐
        │               AGENT RUNTIMES                         │
        │                                                      │
        │  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐  │
        │  │  TS Runtime  │ │ Python Runtm │ │ Kotlin Runtm │  │
        │  │  Mastra +    │ │ FastAPI +    │ │ Ktor +       │  │
        │  │  Vercel AI   │ │ LangChain    │ │ Koog         │  │
        │  │  :9200-9230  │ │ :9240        │ │ :9250        │  │
        │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘  │
        │         │                │                │          │
        │         └────────────────┼────────────────┘          │
        │                         │                            │
        │              ┌──────────▼──────────┐                 │
        │              │   agents/{name}/    │                 │
        │              │   agent.yaml        │                 │
        │              │   prompt.md         │                 │
        │              └─────────────────────┘                 │
        └──────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────┐
        │                TOOL ECOSYSTEM                        │
        │                                                      │
        │  ┌──────────────┐  ┌─────────────────────────────┐   │
        │  │  uap-toolkit │  │   MCP Servers (:9100-9112)  │   │
        │  │  22 modules  │  │   13 servers                │   │
        │  │  83+ tools   │  │   JSON-RPC 2.0              │   │
        │  └──────────────┘  └─────────────────────────────┘   │
        └──────────────────────────────────────────────────────┘
```

---

## 3. Unified Backend

### 3.1 Application Structure

The backend is a single Express.js application created by the factory function `createApp()` in `src/app.ts`. It mounts all 18 feature modules as Express routers on a single process, replacing what was previously 18 independent microservices.

**Entry point:** `src/server.ts` -- creates the app, starts the HTTP server, launches background workers, and registers graceful shutdown handlers.

**File layout:**
```
src/
├── app.ts              # Express factory — mounts all 47 route prefixes
├── server.ts           # HTTP server + background workers + shutdown
├── shared/             # Singletons (1 each replaces 14-17 per-service copies)
│   ├── prisma.ts       # Single PrismaClient
│   ├── redis.ts        # Redis factory with key prefix support
│   └── logger.ts       # Single pino logger
├── middleware/          # Global middleware
│   ├── auth.ts         # JWT validation
│   └── rate-limit.ts   # 3-tier rate limiting
├── platform/           # 7 platform modules
├── builders/           # 6 builder modules
└── runtime/            # 4 runtime modules
```

### 3.2 Middleware Chain

Requests pass through the following middleware in order:

```
Request
  │
  ├─ 1. helmet()              Security headers (CSP disabled for SPA compatibility)
  ├─ 2. cors()                Configurable origins via CORS_ORIGINS env var
  ├─ 3. express.json()        Body parsing (50 MB limit for inference batches)
  ├─ 4. express.urlencoded()  Form data parsing
  ├─ 5. pino-http             Structured request logging (auto-skips /health, /ready, /metrics)
  ├─ 6. authMiddleware        JWT validation (skips PUBLIC_PATHS)
  ├─ 7. Rate limiters         Applied per-prefix (see below)
  │
  └─ Route handlers
```

### 3.3 Rate Limiting

Three rate limiter tiers are applied based on route prefix:

| Tier | Prefix | Window | Max Requests | Key |
|------|--------|--------|-------------|-----|
| Auth | `/api/v1/auth` | 5 min | 20 | IP address |
| Inference | `/api/v1/inference` | 1 min | 500 | User ID or IP |
| Default | `/api/v1/*` | 15 min | 1,000 | User ID or IP |

All limits are configurable via environment variables (`RATE_LIMIT_MAX`, `AUTH_RATE_LIMIT_MAX`, `INFERENCE_RATE_LIMIT_MAX`, etc.).

### 3.4 Shared Singletons

**PrismaClient** (`src/shared/prisma.ts`):
- Single instance, reused via `globalThis` in development to survive HMR reloads.
- Logs slow queries (>200ms) in development mode.
- Exports `disconnectPrisma()` for graceful shutdown.

**Redis** (`src/shared/redis.ts`):
- Factory pattern: `getRedis(keyPrefix)` returns a prefix-scoped ioredis client.
- All clients share the same TCP connection configuration.
- Includes helpers: `setWithTTL`, `get`, `del`, `delByPattern`, `evalScript` (Lua scripting for atomic rate limiting).
- Retry strategy: exponential backoff up to 10 retries, max 5s between attempts.

**Logger** (`src/shared/logger.ts`):
- Single pino logger with structured JSON output.
- Pretty-prints in development (`pino-pretty`).
- Redacts sensitive headers: `authorization`, `cookie`, `x-api-key`.
- Base fields include `service: "unified-agent-platform"` and `version` from package.json.

### 3.5 Route Mounting

All 47 route prefixes are mounted in `src/app.ts`. The mounting order follows a consistent pattern:

```
1. Health checks         /health, /ready (no auth, no rate limiting)
2. Auth middleware        Applied globally (skips public paths)
3. Rate limiters         Applied per-prefix
4. Platform routes       /api/v1/registry, /api/v1/auth, /api/v1/models, ...
5. Builder routes        /api/v1/agents, /api/v1/prompts, /api/v1/tools, ...
6. Runtime routes        /api/v1/sandbox, /a2a, /api/v1/mcp, /api/v1/deployments, ...
7. 404 handler           Catch-all
8. Error handler         Global error boundary
```

---

## 4. Platform Layer

Seven modules providing core platform infrastructure. Each follows the standard layout: `index.ts` (router exports), `types.ts`, `routes/`, `services/`, optional `middleware/`, and `__tests__/`.

### 4.1 Registry

Resource registry with semver versioning, dependency resolution, and Git synchronization.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/registry` | CRUD for registry entries (agents, tools, prompts, MCP servers, etc.) |
| `/api/v1/git` | Git sync: push/pull configs to/from GitHub repositories |

**Data models:** `RegistryEntry`, `RegistryVersion`, `RegistryDependency`, `RegistryRating`

**Key capabilities:**
- Semver versioning with changelog tracking per version
- Dependency graph with version constraints
- Community ratings and reviews
- Git-backed configuration storage with SHA tracking

### 4.2 Auth

OAuth2 authentication (Databricks, GitHub, Google), JWT issuance, RBAC, and API key management.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/auth` | Login, OAuth callbacks (Databricks, Okta, Google) |
| `/api/v1/users` | User CRUD, profile management |
| `/api/v1/teams` | Team creation, membership management |
| `/api/v1/api-keys` | API key CRUD with scoped permissions |

**Data models:** `User`, `Team`, `TeamMember`, `Role`, `UserRole`, `ApiKey`

**RBAC model:**
- Roles have JSON-encoded permissions (`[{resource, action}]`)
- Scopes: GLOBAL, TEAM, PROJECT
- System roles are immutable (`isSystem: true`)
- API keys are SHA-256 hashed, with scoped permissions and optional expiry

### 4.3 Model Gateway

Multi-provider LLM routing with guardrails, per-model rate limiting, and cost calculation.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/models` | Model invocation (sync + streaming), model CRUD |
| `/api/v1/rate-limits` | Per-model rate limit configuration |
| `/api/v1/guardrails` | Guardrail rule CRUD and execution |

**Data models:** `ModelConfig`, `RateLimit`, `GuardrailConfig`

**Supported model types:** TEXT, EMBEDDING, REASONING, IMAGE, VIDEO

**Guardrail types:** PII_DETECTION, CONTENT_FILTER, TOXICITY, HALLUCINATION, CUSTOM

**Guardrail actions:** BLOCK, REDACT, WARN, LOG

### 4.4 Governance

Approval workflows, policy engine, and audit logging for all platform operations.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/approvals` | Approval request CRUD, decision recording |
| `/api/v1/policies` | Policy CRUD (conditions + actions per resource type) |
| `/api/v1/audit` | Audit log queries (filterable by user, resource, action, date) |

**Data models:** `ApprovalRequest`, `ApprovalDecision`, `Policy`, `AuditLog`

**Approval actions:** DEPLOY, UPDATE, DELETE, PUBLISH

**Approval statuses:** PENDING, APPROVED, REJECTED, CANCELED

### 4.5 Monitoring

Health checks, Prometheus metrics exposition, OpenTelemetry trace storage, and alert management.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/health` | Service health checks (periodic background evaluation) |
| `/api/v1/metrics` | Prometheus-format metrics exposition |
| `/api/v1/traces` | Trace query and storage |
| `/api/v1/alerts` | Alert rule CRUD and evaluation |

**Background workers:**
- `health-checker`: periodic health checks (default 30s interval)
- `alert-engine`: periodic alert evaluation (default 60s interval)

### 4.6 Cost Tracker

Usage-based cost tracking per agent, model, user, and team. Budget management with threshold alerts.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/costs` | Cost record queries (filterable, aggregatable) |
| `/api/v1/budgets` | Budget CRUD, threshold configuration |

**Data models:** `CostRecord`, `Budget`, `BudgetAlert`

**Key fields per cost record:** `tokensIn`, `tokensOut`, `costUsd` (12,6 decimal precision), `agentId`, `modelId`, `userId`, `teamId`

**Background workers:**
- `budget-service`: monthly budget reset cron job

### 4.7 Inference Capture

Ring buffer capture of inference requests/responses with PII redaction and S3/MinIO export.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/inference` | Capture ingestion, query, export management |

**Data models:** `InferenceRecord`

**Design:** Full payloads are stored in object storage (S3 or MinIO). The database stores only previews, hashes, token counts, latency, and cost. This enables cost-effective long-term storage with fast querying.

**Background workers:**
- `capture-service`: periodic buffer flushing
- `export-service`: scheduled S3 exports

---

## 5. Builder Layer

Six modules providing tools for creating, testing, and managing agent components.

### 5.1 Agent Builder

YAML-to-code generation across 14 generators (8 Python + 6 TypeScript), template management, toolkit browsing, and Git sync.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/agents` | Agent CRUD, filesystem operations, code generation, Git sync, GitHub Actions |
| `/api/v1/templates` | Agent template browsing and instantiation |
| `/api/v1/toolkit` | Toolkit tool listing and metadata |

**Code generators (14):**

| Language | Frameworks |
|----------|-----------|
| Python | LangChain, LangGraph, CrewAI, OpenAI SDK, Claude SDK, Google ADK, Strands SDK, Pydantic AI |
| TypeScript | Mastra, LangChain, LangGraph, OpenAI SDK, Claude SDK, Google ADK |

### 5.2 Prompt Builder

Prompt versioning, template variables, testing with model invocation, and Git sync.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/prompts` | Prompt CRUD, version management, test execution, Git sync |

### 5.3 Tool Builder

Tool CRUD, sandboxed execution (Docker isolation), dependency resolution, and Git sync.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/tools` | Tool CRUD, execution, dependency resolution, Git sync |

**Capabilities:**
- Schema generation from tool code (Zod-based `ToolContract<TInput, TOutput>`)
- Dependency resolution between tools
- Sandboxed execution via the Sandbox runtime module

### 5.4 RAG Builder

Vector collection management across 6 providers, document ingestion, and semantic search.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/vector-collections` | Collection CRUD, document ingestion, semantic query |
| `/api/v1/collections` | Git sync for collection configs |

**Data models:** `VectorCollection`

**Supported providers:** Databricks, Elasticsearch, pgvector, Pinecone, Weaviate, Qdrant

### 5.5 Memory Builder

Conversation memory configuration, conversation management, and message storage.

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/memory-configs` | Memory configuration CRUD |
| `/api/v1/conversations` | Conversation lifecycle management |
| `/api/v1/memory` | Message storage and retrieval |

**Data models:** `MemoryConfig`, `Conversation`, `Message`

**Memory types:** buffer_window, buffer, summary, entity, vector_store

**Backends:** in_memory, redis, postgresql

### 5.6 Marketplace

Browse, install, fork, and review shared artifacts (agents, tools, prompts, etc.).

| Route Prefix | Key Endpoints |
|-------------|---------------|
| `/api/v1/marketplace` | Browse catalog, submit reviews, install/fork artifacts |

---

## 6. Runtime Layer

Four modules providing execution infrastructure for agents and tools.

### 6.1 Sandbox

Docker-based isolated code execution supporting Python, TypeScript, and Kotlin.

**Key routes:** `/api/v1/sandbox/execute`, `/api/v1/sandbox/status`

**Capabilities:**
- Pre-warmed Docker images for fast cold starts
- Execution timeout enforcement
- Resource limits (CPU, memory)
- Automatic container cleanup loop

**Background workers:**
- `image-manager`: warmup loop (pre-pull images) + cleanup loop (remove stale containers)
- `executor`: manages running executions, supports `cancelAll()` on shutdown

### 6.2 A2A Server

Agent-to-Agent communication via JSON-RPC 2.0, implementing the A2A protocol.

**Key routes:** `/a2a/respond`, `/message/send`, `/api/v1/a2a/registry`

**Task lifecycle:** `SUBMITTED` -> `WORKING` -> `COMPLETED` (or `FAILED`)

**Background workers:**
- `task-store`: cleanup loop for expired/completed tasks

### 6.3 MCP Server

MCP (Model Context Protocol) server registry, JSON-RPC 2.0 tool discovery and execution.

**Key routes:** `/api/v1/mcp/servers`, `/api/v1/mcp/tools`

**Background workers:**
- `mcp-service`: periodic health checks on registered MCP servers

### 6.4 Deployer

Multi-target deployment engine supporting 10 deployment targets.

**Key routes:** `/api/v1/deployments`, `/api/v1/platform/deploy`

**Data models:** `Deployment`, `DeploymentLog`

**Deployment targets (10):**

| Target | Infrastructure |
|--------|---------------|
| EKS | AWS Elastic Kubernetes Service |
| GKE | Google Kubernetes Engine |
| Fargate | AWS Fargate (serverless containers) |
| Cloud Run | Google Cloud Run |
| Azure Container Apps | Azure Container Apps |
| OKE | Oracle Kubernetes Engine |
| Bedrock | AWS Bedrock (managed agent hosting) |
| Databricks Apps | Databricks serverless apps |
| Docker | Local Docker deployment |
| Kubernetes | Generic Kubernetes |

**Deployment statuses:** PENDING -> BUILDING -> DEPLOYING -> RUNNING (or FAILED, STOPPED)

---

## 7. Agent Runtime Architecture

### 7.1 Three Runtimes Side-by-Side

| Dimension | TypeScript | Python | Kotlin |
|-----------|-----------|--------|--------|
| **Package** | `agent-runtime/` | `agent-runtime-python/` | `agent-runtime-kotlin/` |
| **Framework** | Mastra + Vercel AI SDK | FastAPI + LangChain/LangGraph | Ktor + Koog |
| **Language** | TypeScript (ESM) | Python 3.12 | Kotlin (JVM 21) |
| **Build** | `tsx` / `tsc` | `uvicorn` | Gradle shadow JAR |
| **Base image** | `node:22-slim` | `python:3.12-slim` | `eclipse-temurin:21-jre` |
| **Port range** | 9200-9230 | 9240 | 9250 |
| **Hot reload** | `tsx --watch` | `uvicorn --reload` | Gradle continuous build |

All three runtimes share the same internal pipeline:

```
agent.yaml ──► config-loader ──► agent-factory ──► model-factory
                                      │
                                      ├── tool-loader (dotted paths → functions)
                                      ├── mcp-loader (MCP server connections)
                                      ├── vector-search-factory (auto-tools)
                                      ├── subagent-loader (HTTP call tools)
                                      └── memory-factory (backend selection)
                                      │
                                      ▼
                                   routes
                                  /invocations
                                  /invocations/stream
                                  /health
                                  /info
```

### 7.2 Config Loading (5-Layer Merge)

The config loader implements a 5-layer merge hierarchy with environment variable substitution:

```
Priority (lowest → highest):
  1. agents/@global/agent.yaml              Global defaults
  2. agents/@global/agent.{NODE_ENV}.yaml   Global environment override
  3. agents/{name}/agent.yaml               Agent-specific config
  4. agents/{name}/agent.{NODE_ENV}.yaml    Agent environment override
  5. agents/{name}/agent.local.yaml         Local developer override (gitignored)
```

**Merge semantics:**
- Default: lists replace, dicts merge recursively, primitives replace
- `+key` prefix: append items to existing list instead of replacing
- `^key` prefix: replace entire dict instead of recursive merge
- `${ENV_VAR}` placeholders are substituted from `process.env`

**Validation:** Merged config is validated against a Zod schema (`agentConfigSchema`) that covers all supported fields.

### 7.3 Model Factory (18 Providers)

The model factory dynamically imports provider SDKs based on the `provider` field in agent YAML. Provider resolution follows a 4-tier priority:

```
1. First-party SDKs     anthropic, openai, google, bedrock, azure
2. Model Gateway         gateway (routes through UAP's own gateway)
3. OpenAI-compatible     databricks, litellm, openrouter, together, fireworks,
                         perplexity, xai, deepseek, moonshot, groq, mistral, cohere
4. Generic fallback      Any provider with explicit base_url
```

Generation parameters (temperature, max_tokens, top_p, top_k, etc.) are applied at generate-time via `buildGenerateOptions()`, not at model construction, ensuring they work consistently across all providers.

### 7.4 Tool Loading Pipeline

Tools are loaded from four sources and merged into a single `allTools` map:

1. **Toolkit tools** -- dotted path strings (e.g., `uap_toolkit.databricks.query.submit_query`) resolved from the `uap-toolkit` package registry
2. **Subagent tools** -- auto-generated HTTP call tools from `subagents:` YAML entries
3. **Vector search tools** -- auto-generated `search_{index_name}` tools from `vector_search_indexes:` YAML entries (Databricks REST API or Elasticsearch kNN/hybrid)
4. **MCP tools** -- tools discovered from configured MCP servers via JSON-RPC 2.0

### 7.5 Memory Architecture

Memory is configured in agent YAML and created by the memory factory:

```yaml
memory:
  type: buffer_window      # buffer_window | buffer | summary | entity | vector_store
  backend: redis            # in_memory | redis | postgresql
  max_messages: 20
  semantic_recall:
    enabled: true
    top_k: 5
    score_threshold: 0.7
```

The runtime manages memory in the route handlers:
1. User message is added to the session before agent invocation
2. Conversation history is loaded (up to `max_messages`)
3. Optional semantic recall prepends relevant past messages
4. Agent response is saved to the session after invocation

### 7.6 HTTP API Contract

Every agent (regardless of runtime) exposes the same HTTP API:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check, returns `ok` |
| `/ready` | GET | Readiness check, returns `ok` |
| `/info` | GET | Agent metadata (name, version, tools, subagents) |
| `/invocations` | POST | Synchronous invocation |
| `/invocations/stream` | POST | Streaming invocation (SSE) |

**Request body:**
```json
{
  "prompt": "User message",
  "session_id": "optional-conversation-id",
  "...": "additional context fields"
}
```

**Sync response:**
```json
{
  "result": "Agent response text",
  "session_id": "conversation-id"
}
```

**Stream response (SSE):**
```
data: {"type": "delta", "content": "partial"}
data: {"type": "delta", "content": " response"}
data: {"type": "done", "content": "full response", "session_id": "..."}
data: [DONE]
```

### 7.7 Retry and Fallback

The runtime supports automatic retry with exponential backoff and fallback models:

```yaml
model:
  provider: anthropic
  name: claude-sonnet-4-5
  retry:
    max_attempts: 3
    backoff_factor: 2.0
    jitter: true
  fallback_model:
    provider: openai
    name: gpt-4o
```

On primary model failure, the runtime retries up to `max_attempts` with exponential backoff. If all retries fail and a `fallback_model` is configured, a new agent instance is created with the fallback model and the request is retried once.

### 7.8 Guardrails, Hooks, and Tracing

**Input/output guardrails:** Applied before and after model invocation. Types include `content_policy` and `pii_redaction`. Actions: `block` (reject request) or `warn` (pass through with warning).

**Hooks:** `before_model` and `after_model` hooks reference toolkit functions that are called synchronously in the request pipeline.

**Tracing:** When `tracing.enabled: true`, the runtime creates OpenTelemetry spans for each invocation with attributes for agent name, model, and session ID.

---

## 8. Tool Ecosystem

### 8.1 Toolkit Registry

The `uap-toolkit/` package contains 83+ pre-built tool functions organized in 22 modules. Tools are referenced in agent YAML by dotted path:

```yaml
tools:
  - uap_toolkit.zendesk.search_help_articles
  - uap_toolkit.databricks.query.submit_query
  - uap_toolkit.cip.content_quality.assess_professionalism
```

**Module inventory:**

| Module | Tools | Description |
|--------|-------|-------------|
| `zendesk` | 1 | Help article search via MCP |
| `course_catalog` | 2 | Course search via MCP |
| `featurestore` | 2 | Feature store queries via MCP |
| `learner_state` | 2 | Learner progress via MCP |
| `learner_state_agent` | 1 | Learner state agent call via MCP |
| `learner_profile` | 2 | Learner profiles via MCP |
| `goal_elicitation` | 2 | Goal elicitation via MCP |
| `tutor` | 1 | Tutoring via MCP |
| `s3_persist` | 2 | S3 persistence via MCP |
| `execute_query` | 1 | SQL execution via MCP |
| `onboarding` | 1 | Onboarding via MCP |
| `lecture_lo` | 2 | Lecture learning objectives via MCP |
| `inline` | 2 | Calculator + echo (no MCP dependency) |
| `memory` | 3 | Conversation memory (store/retrieve/search) |
| `databricks.query` | 2 | Submit + retrieve SQL queries |
| `databricks.user` | 1 | Current user info |
| `databricks.lineage` | 2 | Table + column lineage |
| `databricks.job` | 4 | Job listing, runs, details |
| `atlassian` | 4 | Jira issues + Confluence wiki |
| `airflow.dag` | 9 | DAG operations via Lambda proxy |
| `common` | 2 | Sleep + echo |
| `taxonomy` | 1 | Save topic recommendation |
| `cip.content_quality` | 10 | 8-dimension quality scoring |

The registry supports multi-level dotted paths via three registration loops (single-level, flat, and nested) in the index module.

### 8.2 MCP Servers

13 MCP servers run on ports 9100-9112, each exposing tools via JSON-RPC 2.0:

```
Port 9100-9112: zendesk, course-catalog, featurestore, learner-state,
                learner-profile, goal-elicitation, tutor, s3-persist,
                execute-query, onboarding, lecture-lo, learner-state-agent,
                ...
```

MCP servers are standalone processes that can be discovered and called by the MCP Server runtime module or directly by agent runtimes via the `mcps:` YAML config.

### 8.3 Vector Search Auto-Tools

Agents can declare `vector_search_indexes` in YAML and the runtime auto-generates search tools:

**Databricks Vector Search:**
```yaml
vector_search_indexes:
  - index_name: prod.schema.my_index
    num_results: 5
    query_type: HYBRID
    columns: ["id", "content", "metadata"]
```
Calls Databricks REST API `/api/2.0/vector-search/indexes/{name}/query` with auto-embedded query text.

**Elasticsearch:**
```yaml
vector_search_indexes:
  - index_name: my-knowledge-base
    provider: elasticsearch
    num_results: 10
    query_type: HYBRID
    dimensions: 1536
    metric: cosine
```
Uses kNN search for pure vector, or combined kNN + BM25 (0.7/0.3 boost) for hybrid mode.

### 8.4 Subagent Tools

Subagents declared in YAML are auto-converted to HTTP call tools:

```yaml
subagents:
  - agent_name: helper-agent
    tool_name: ask_helper
    description: Delegate complex questions to the helper agent
```

The loader generates a tool that makes HTTP POST requests to the subagent's `/invocations` endpoint.

---

## 9. Data Model

### 9.1 Overview

PostgreSQL 16 with pgvector extension. Single Prisma schema at `db/schemas/schema.prisma` with 27 models and 19 enums.

### 9.2 Model Groups

```
┌─────────────────────────────────────────────────────────────┐
│                      REGISTRY                               │
│  RegistryEntry ──┬── RegistryVersion                        │
│                  ├── RegistryDependency                      │
│                  ├── RegistryRating ──── User                │
│                  └── Deployment                              │
├─────────────────────────────────────────────────────────────┤
│                    AUTH & RBAC                               │
│  User ──┬── TeamMember ──── Team                            │
│         ├── UserRole ──── Role                              │
│         ├── ApiKey                                          │
│         └── (relations to most other models)                │
├─────────────────────────────────────────────────────────────┤
│                    GOVERNANCE                               │
│  ApprovalRequest ──── ApprovalDecision                      │
│  Policy                                                     │
│  AuditLog                                                   │
├─────────────────────────────────────────────────────────────┤
│                  MODEL GATEWAY                              │
│  ModelConfig ──── RateLimit                                 │
│  GuardrailConfig                                            │
├─────────────────────────────────────────────────────────────┤
│                  COST TRACKING                              │
│  CostRecord                                                 │
│  Budget ──┬── BudgetAlert                                   │
│           └── Team                                          │
├─────────────────────────────────────────────────────────────┤
│               INFERENCE CAPTURE                             │
│  InferenceRecord                                            │
├─────────────────────────────────────────────────────────────┤
│                  DEPLOYMENTS                                │
│  Deployment ──── DeploymentLog                              │
├─────────────────────────────────────────────────────────────┤
│                    MEMORY                                   │
│  MemoryConfig                                               │
│  Conversation ──── Message                                  │
├─────────────────────────────────────────────────────────────┤
│               VECTOR COLLECTIONS                            │
│  VectorCollection                                           │
└─────────────────────────────────────────────────────────────┘
```

### 9.3 Key Enums

| Enum | Values |
|------|--------|
| `ResourceType` | AGENT, TOOL, PROMPT, MCP_SERVER, VECTOR_COLLECTION, MODEL, MEMORY_CONFIG |
| `Language` | PYTHON, TYPESCRIPT, KOTLIN |
| `Framework` | LANGCHAIN, LANGGRAPH, MASTRA, CREWAI, OPENAI_SDK, GOOGLE_ADK, CLAUDE_SDK, STRANDS_SDK, PYDANTIC_AI, AUTOGEN, KOOG, NONE |
| `AuthProvider` | DATABRICKS, GITHUB, GOOGLE |
| `DeploymentTarget` | EKS, DATABRICKS_APP, GKE |
| `DeploymentStatus` | PENDING, BUILDING, DEPLOYING, RUNNING, FAILED, STOPPED |
| `GuardrailType` | PII_DETECTION, CONTENT_FILTER, TOXICITY, HALLUCINATION, CUSTOM |
| `GuardrailAction` | BLOCK, REDACT, WARN, LOG |
| `VectorProvider` | DATABRICKS, ELASTIC, PGVECTOR, PINECONE, WEAVIATE, QDRANT |
| `ModelType` | TEXT, EMBEDDING, REASONING, IMAGE, VIDEO |
| `MessageRole` | SYSTEM, USER, ASSISTANT, TOOL |

### 9.4 Key Relationships

- `User` is the central entity, with relations to nearly all other models (registry entries, deployments, conversations, API keys, teams, approvals, etc.)
- `RegistryEntry` uses a composite unique constraint on `(resourceType, name, version)` for semver-aware deduplication
- `Deployment` links a `RegistryEntry` to infrastructure via `DeploymentTarget`
- `Budget` is scoped to `Team`, with `BudgetAlert` tracking threshold breach notifications
- All UUIDs are server-generated via `gen_random_uuid()`

---

## 10. Frontend Architecture

### 10.1 Overview

React 19 SPA built with Vite, served on port 3000. The frontend communicates with the unified backend on port 8080 via REST API calls.

### 10.2 Structure

```
ui/
├── src/
│   ├── features/              # 13 feature areas
│   │   ├── agent-builder/     # 4-mode agent builder (Visual, YAML, Prompt, IDE)
│   │   ├── dashboard/         # Overview dashboard
│   │   ├── deployments/       # Deployment management
│   │   ├── agents/            # Agent registry browsing
│   │   ├── tools/             # Tool management
│   │   ├── prompts/           # Prompt management
│   │   ├── models/            # Model configuration
│   │   ├── monitoring/        # Health and metrics dashboards
│   │   ├── cost/              # Cost tracking dashboard
│   │   ├── governance/        # Approval workflows
│   │   ├── marketplace/       # Artifact marketplace
│   │   ├── settings/          # User and team settings
│   │   └── chat/              # Agent chat interface
│   ├── components/            # 12+ reusable UI components
│   ├── hooks/                 # Custom React hooks
│   ├── lib/                   # API client, utilities
│   └── stores/                # Zustand stores
├── e2e/                       # Playwright E2E tests
└── vite.config.ts
```

### 10.3 State Management

- **TanStack React Query** -- Server state (API data caching, stale-while-revalidate)
- **Zustand** -- Client state (UI toggles, agent builder state, undo/redo stacks)

### 10.4 Agent Builder

The agent builder (`ui/src/features/agent-builder/`) is the most complex UI feature, supporting four editing modes mapped to the 3-tier authoring model:

| Mode | Tier | Components |
|------|------|-----------|
| Visual | No-Code | ReactFlow graph with 10 node types (Agent, Model, Prompt, Tool, Subagent, Memory, RAG, MCP, A2A, Guardrail) |
| YAML | Low-Code | Monaco editor with schema completions, insert snippets, validation markers |
| Prompt | Low-Code | Markdown editor with live preview for `prompt.md` |
| IDE | Full Code | Code generator (14 generators), language/framework selector, sandbox execution, AI assistant, ZIP export |

**Key features:** Undo/redo (50-entry stacks), version history, test panel, toolkit tool picker, import/export, filesystem CRUD.

### 10.5 Testing

- **Unit tests:** Vitest + Testing Library + jsdom
- **E2E tests:** Playwright (specs in `ui/e2e/`)
- **Coverage:** 80% thresholds enforced

---

## 11. Deployment Architecture

### 11.1 Local Development (Docker Compose)

`deploy/docker-compose.yml` defines the full local environment:

```
Infrastructure:
  postgres      pgvector/pgvector:pg16     :5432
  redis         redis:7-alpine             :6379
  minio         MinIO (S3-compatible)      :9000

Platform:
  unified-app   Express.js (all modules)   :8080
  ui            React SPA (Vite dev)       :3000

Agents (shared runtime images):
  agent-*       TS runtime                 :9200-9230
  agent-*       Python runtime             :9240
  agent-*       Kotlin runtime             :9250

MCP Servers:
  mcp-*         13 servers                 :9100-9112

Observability:
  prometheus    Prometheus                 :9090
  grafana       Grafana                    :3001
```

Resource limits: 1 CPU / 512MB per service (2 CPU / 1GB for PostgreSQL).

### 11.2 Kubernetes (Helm + ArgoCD)

**Helm chart:** `deploy/helm/unified-agent-platform/` (nodejs-app-chart)

**ArgoCD manifests:** `deploy/argocd/` with Application definitions for 3 environments:
- `dev`
- `prod-useast1`
- `prod-uswest2`

### 11.3 Terraform

Infrastructure-as-code under `deploy/terraform/`:

| Directory | Purpose |
|-----------|---------|
| `dev/` | Development environment |
| `prod-useast1/` | Production US East |
| `prod-uswest2/` | Production US West |
| `eks/` | AWS EKS cluster |
| `gke/` | Google GKE cluster |
| `rds/` | AWS RDS PostgreSQL |
| `s3/` | AWS S3 buckets |
| `elasticache/` | AWS ElastiCache Redis |

### 11.4 CI/CD

GitHub Actions workflow for automated deployments. Pipeline stages:
1. Lint and type check
2. Unit tests with coverage enforcement (80% thresholds)
3. Integration tests
4. Docker image build
5. Deploy to target environment

### 11.5 Docker Images

| Image | Base | Contents |
|-------|------|----------|
| `unified-agent-platform` | node:22-slim | Unified backend (all 18 modules) |
| `uap-agent-runtime` | node:22-slim | TypeScript agent runtime (serves any agent) |
| `uap-agent-runtime-python` | python:3.12-slim | Python agent runtime |
| `uap-agent-runtime-kotlin` | eclipse-temurin:21-jre | Kotlin agent runtime (shadow JAR) |
| `uap-ui` | node:22-slim | React SPA (Vite build) |

---

## 12. Observability

### 12.1 Logging

- **Library:** pino (structured JSON)
- **Request logging:** pino-http with custom log levels (500+ = error, 400+ = warn, else info)
- **Request IDs:** Propagated via `X-Request-Id` header or auto-generated (`uap-{timestamp}-{random}`)
- **Redaction:** Authorization, cookie, and API key headers are redacted from logs
- **Development:** Pretty-printed with colors via pino-pretty

### 12.2 Metrics

- **Exposition:** Prometheus format on `/metrics` and `/api/v1/metrics`
- **Collection:** Prometheus scrapes at configurable interval (default 15s)
- **Dashboards:** Grafana with pre-configured dashboards under `observability/`

### 12.3 Tracing

- **Protocol:** OpenTelemetry (OTel)
- **Agent spans:** Auto-created per invocation when `tracing.enabled: true` in agent YAML
- **Attributes:** `agent.name`, `agent.model`, `agent.session_id`
- **Collector:** OTel Collector configuration in `observability/`

### 12.4 Health Checks

Two unauthenticated endpoints are always available:

```
GET /health    → { status: "healthy", service, timestamp, uptime }
GET /ready     → { status: "ready",   service, timestamp }
```

The monitoring module runs periodic health checks against registered services (configurable interval, default 30s).

### 12.5 Alerting

The alert engine evaluates alert rules on a configurable interval (default 60s). Alert rules are managed via the `/api/v1/alerts` API.

---

## 13. Security

### 13.1 Authentication

**JWT validation** (`src/middleware/auth.ts`):
- Supports HS256 and RS256 algorithms
- Token extracted from `Authorization: Bearer <token>` header
- Decoded payload fields (`sub`, `email`, `roles`) injected into request headers for downstream handlers
- Specific error responses for expired tokens vs. invalid tokens

**Public paths** (no auth required):
- `/health`, `/ready`, `/metrics`
- `/api/v1/auth/login/*`, `/api/v1/auth/callback/*`

**OAuth2 providers:** Databricks, GitHub (via Okta), Google

**API keys:** SHA-256 hashed, scoped permissions, optional expiry, last-used tracking

### 13.2 Authorization (RBAC)

- Roles with JSON-encoded permissions: `[{resource: "agents", action: "deploy"}]`
- Three scopes: GLOBAL, TEAM, PROJECT
- System roles are immutable
- Team membership with roles: ADMIN, MEMBER, VIEWER

### 13.3 Rate Limiting

Three tiers with configurable limits (see section 3.3). Rate limiter keys are per-user when authenticated, per-IP otherwise. Standard rate limit headers (`RateLimit-*`) are included in responses.

### 13.4 Guardrails

Two layers of guardrail enforcement:

1. **Platform level** (Model Gateway): `GuardrailConfig` in the database, applied to all invocations through the gateway
2. **Agent level** (Runtime): Input and output guardrails declared in agent YAML, applied in the request pipeline

**Types:** PII detection, content filtering, toxicity detection, hallucination detection, custom rules

### 13.5 PII Redaction

- **Logs:** Sensitive headers (authorization, cookie, x-api-key) are redacted by pino
- **Inference capture:** PII redaction applied before storage in the inference capture module
- **Guardrails:** PII redaction guardrail available as both platform and agent-level protection

### 13.6 Security Headers

Helmet.js applies standard security headers (X-Content-Type-Options, X-Frame-Options, etc.). CSP and COEP are disabled for SPA compatibility.

---

## 14. Background Workers

All background workers are started in `src/server.ts` after the HTTP server begins listening, and stopped during graceful shutdown.

| Worker | Module | Interval | Purpose |
|--------|--------|----------|---------|
| `startPeriodicHealthChecks` | Monitoring | 30s | Evaluate registered service health |
| `startAlertEvaluation` | Monitoring | 60s | Evaluate alert rules against metrics |
| `startBudgetResetCron` | Cost Tracker | Monthly | Reset monthly budget spend counters |
| `startBufferFlushing` | Inference Capture | Periodic | Flush in-memory inference buffer to database |
| `startScheduledExports` | Inference Capture | Scheduled | Export inference records to S3/MinIO |
| `imageManager.warmup` | Sandbox | On startup | Pre-pull Docker images for sandbox execution |
| `imageManager.startCleanupLoop` | Sandbox | Periodic | Remove stale sandbox containers |
| `taskStore.startCleanupLoop` | A2A Server | Periodic | Remove expired/completed A2A tasks |
| `mcpService.startHealthChecks` | MCP Server | Periodic | Health-check registered MCP servers |

### Graceful Shutdown Sequence

```
Signal received (SIGTERM/SIGINT)
  │
  ├─ 1. Stop accepting new HTTP connections
  ├─ 2. Stop all background workers
  │      ├─ stopPeriodicHealthChecks()
  │      ├─ stopAlertEvaluation()
  │      ├─ stopBufferFlushing()
  │      ├─ taskStore.stopCleanupLoop()
  │      └─ mcpService.stopHealthChecks()
  ├─ 3. Force flush inference buffer
  ├─ 4. Cancel running sandbox executions
  ├─ 5. Close MCP connections
  ├─ 6. Disconnect Redis (all prefixed clients)
  ├─ 7. Disconnect Prisma
  │
  └─ Exit 0 (or force exit after 15s timeout)
```

---

## 15. Data Flow Diagrams

### 15.1 Agent Invocation (Sync)

```
Client
  │
  │ POST /invocations { prompt, session_id }
  │
  ▼
Agent Runtime (any of 3)
  │
  ├─ 1. Apply input guardrails (block/warn)
  ├─ 2. Add user message to memory (if session_id)
  ├─ 3. Load conversation history (up to max_messages)
  ├─ 4. Semantic recall (if configured)
  ├─ 5. Call before_model hook
  ├─ 6. Invoke LLM with tools
  │      ├─ LLM may call tools (up to max_iterations cycles)
  │      │   ├─ Toolkit tools (local functions)
  │      │   ├─ MCP tools (JSON-RPC to MCP server)
  │      │   ├─ Vector search tools (Databricks/ES API)
  │      │   └─ Subagent tools (HTTP to other agent)
  │      └─ Retry with backoff on failure
  │          └─ Fallback to alternate model if configured
  ├─ 7. Call after_model hook
  ├─ 8. Apply output guardrails (block/warn/redact)
  ├─ 9. Save assistant message to memory
  │
  ▼
Client receives { result, session_id }
```

### 15.2 Agent Deployment

```
UI / API Client
  │
  │ POST /api/v1/deployments
  │ { agentId, target, config }
  │
  ▼
Deployer Module
  │
  ├─ 1. Validate config and check governance policies
  ├─ 2. Create Deployment record (status: PENDING)
  ├─ 3. Check for approval requirement
  │      ├─ If required: create ApprovalRequest, wait
  │      └─ If not: proceed
  ├─ 4. Build Docker image (status: BUILDING)
  │      └─ Select base image (TS/Python/Kotlin runtime)
  ├─ 5. Push to container registry
  ├─ 6. Deploy to target (status: DEPLOYING)
  │      ├─ EKS: kubectl apply (Deployment + Service + Ingress)
  │      ├─ GKE: gcloud run deploy
  │      ├─ Databricks: apps deploy
  │      └─ ... (10 targets)
  ├─ 7. Wait for health check (status: RUNNING)
  ├─ 8. Record deployment logs
  │
  ▼
Deployment record updated with endpoint URL
```

### 15.3 A2A Communication

```
Agent A (caller)
  │
  │ Tool call: ask_agent_b(prompt)
  │
  ▼
Subagent Tool (HTTP client)
  │
  │ POST http://agent-b:9201/invocations
  │ { prompt, session_id }
  │
  ▼
Agent B (callee)
  │
  ├─ Process as normal invocation
  ├─ May call its own tools/subagents
  │
  ▼
Response flows back:
  Agent B → Subagent Tool → Agent A → continues reasoning
```

For formal A2A protocol (JSON-RPC 2.0):

```
Agent A
  │
  │ POST /a2a/respond or /message/send
  │ { jsonrpc: "2.0", method: "tasks/send", params: { ... } }
  │
  ▼
A2A Server
  │
  ├─ Create task (status: SUBMITTED)
  ├─ Route to target agent (status: WORKING)
  ├─ Agent processes and responds (status: COMPLETED)
  │
  ▼
Task result returned to caller
```

### 15.4 Model Gateway Invocation

```
Agent Runtime / Client
  │
  │ POST /api/v1/models/invoke
  │ { model, messages, parameters }
  │
  ▼
Model Gateway
  │
  ├─ 1. Check per-model rate limits (Redis Lua script)
  ├─ 2. Apply guardrails (PII, content filter, toxicity)
  ├─ 3. Route to provider
  │      ├─ Anthropic (Claude)
  │      ├─ OpenAI (GPT)
  │      ├─ Google (Gemini)
  │      ├─ Databricks (Foundation Models)
  │      └─ ... (18 providers)
  ├─ 4. Calculate cost (tokens * provider rate)
  ├─ 5. Record cost event
  ├─ 6. Capture inference record (ring buffer → S3)
  │
  ▼
Response returned to caller
```

### 15.5 Inference Capture Pipeline

```
Model Gateway response
  │
  ├─ 1. Extract token counts, latency, cost
  ├─ 2. PII redaction on input/output previews
  ├─ 3. Write to ring buffer (in-memory)
  │
  ▼
Buffer Flush Worker (periodic)
  │
  ├─ 4. Batch insert InferenceRecord rows (previews + metadata)
  ├─ 5. Write full payloads to S3/MinIO
  │
  ▼
Export Worker (scheduled)
  │
  └─ 6. Export batches to long-term S3 storage
```

---

## Port Reference

| Port | Service |
|------|---------|
| 3000 | UI (React SPA) |
| 5432 | PostgreSQL |
| 6379 | Redis |
| 8080 | Unified Agent Platform (all 47 API routes) |
| 9090 | Prometheus |
| 9100-9112 | MCP Servers (13 servers) |
| 9200-9230 | Agents (TypeScript runtime) |
| 9240 | Agents (Python runtime) |
| 9250 | Agents (Kotlin runtime) |

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `8080` | HTTP server port |
| `HOST` | `0.0.0.0` | HTTP server bind address |
| `DATABASE_URL` | -- | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `JWT_SECRET` / `AUTH_SECRET` | `development-secret` | JWT signing key |
| `LOG_LEVEL` | `info` | Pino log level |
| `NODE_ENV` | -- | Environment name (development/production) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `SHUTDOWN_TIMEOUT_MS` | `15000` | Graceful shutdown timeout |
| `HEALTH_CHECK_INTERVAL_MS` | `30000` | Health check frequency |
| `ALERT_EVAL_INTERVAL_MS` | `60000` | Alert evaluation frequency |
| `RATE_LIMIT_MAX` | `1000` | Default rate limit (per 15 min) |
| `AUTH_RATE_LIMIT_MAX` | `20` | Auth rate limit (per 5 min) |
| `INFERENCE_RATE_LIMIT_MAX` | `500` | Inference rate limit (per 1 min) |
| `AGENT_NAME` | -- | Agent name for runtime (selects config directory) |
| `CONFIG_BASE_DIR` | `../agents` | Base directory for agent configs |
| `DATABRICKS_HOST` | -- | Databricks workspace URL |
| `DATABRICKS_TOKEN` | -- | Databricks PAT |
| `MODEL_GATEWAY_URL` | `http://localhost:8003` | Model gateway endpoint |

---

## Design Decisions

### Why a unified process?

Consolidating 18 microservices into a single Express app eliminated:
- 14-17 duplicate PrismaClient instances
- 14-17 duplicate Redis connections
- 14-17 duplicate pino loggers
- Inter-service HTTP overhead (replaced with direct function calls)
- 18 separate Docker images, Helm charts, and CI pipelines

The unified app still maintains module boundaries via the standard feature module structure (`index.ts` exporting routers), making it straightforward to extract modules back into separate services if scaling demands it.

### Why Mastra + Vercel AI SDK for TypeScript?

- Native TypeScript, no Python bridge
- AI SDK provides a unified interface across 18+ LLM providers
- Mastra adds agent orchestration (tools, memory, streaming) on top
- Hot-reloadable agent configs without rebuilding

### Why three runtimes?

Team language preferences vary. The shared YAML config format ensures consistent agent behavior regardless of runtime. The TypeScript runtime is the primary one; Python and Kotlin runtimes support teams with existing investments in those ecosystems.

### Why dotted-path tool references?

- Avoids import path coupling between agent configs and tool implementations
- Supports multi-level namespaces (e.g., `uap_toolkit.databricks.query.submit_query`)
- Tools can be reorganized without changing agent configs
- Runtime resolves paths to functions at startup, failing fast on typos

### Why 5-layer config merge?

- Global defaults reduce boilerplate across 30 agents
- Per-environment overrides handle dev/staging/prod differences without branching
- Local overrides (gitignored) allow developers to customize without affecting others
- Merge prefixes (`+key`, `^key`) provide fine-grained control over list and dict merging
