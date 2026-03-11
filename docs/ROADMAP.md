# UAP Roadmap

Comprehensive roadmap for the Udemy Agent Platform (UAP) — an enterprise platform for building, testing, deploying, and operating AI agents across three authoring tiers (No-Code, Low-Code, Full Code) and three runtimes (TypeScript, Python, Kotlin).

Last updated: 2026-03-10

---

## Table of Contents

1. [Project Vision](#project-vision)
2. [What's Built (Complete)](#whats-built-complete)
3. [Phase 1: Production Hardening](#phase-1-production-hardening-planned)
4. [Phase 2: Agent Evaluation & Quality](#phase-2-agent-evaluation--quality-planned)
5. [Phase 3: Developer Experience](#phase-3-developer-experience-planned)
6. [Phase 4: Enterprise Features](#phase-4-enterprise-features-planned)
7. [Phase 5: Advanced Agent Patterns](#phase-5-advanced-agent-patterns-planned)
8. [Phase 6: Ecosystem & Integration](#phase-6-ecosystem--integration-planned)
9. [Phase 7: Performance & Scale](#phase-7-performance--scale-planned)
10. [How to Recreate This Project From Scratch](#how-to-recreate-this-project-from-scratch)

---

## Project Vision

UAP is a single platform where any engineer can go from idea to production AI agent in minutes. The three-tier authoring model (No-Code visual builder, Low-Code YAML+prompt, Full Code standalone project) means every skill level is supported. All tiers produce agents with the same HTTP API (`/invocations`, `/invocations/stream`) and the same deployment model (Docker container deployed to EKS/GKE/Databricks via a unified deployer).

The platform provides everything around the agent: model routing, tool execution, memory, guardrails, cost tracking, governance, monitoring, and a marketplace for sharing.

---

## What's Built (COMPLETE)

### Core Platform (COMPLETE)

The unified Express.js application consolidates 18 feature modules into a single process on port 8080.

- [x] Unified Express app factory (`src/app.ts`) mounting 47 route prefixes
- [x] HTTP server entry point (`src/server.ts`) with background workers
- [x] Shared singletons: single PrismaClient, Redis factory with key prefix support, pino logger
- [x] JWT authentication middleware with token validation
- [x] OAuth2 provider support (Databricks, GitHub, Google)
- [x] Role-based access control (RBAC) with roles, teams, and API keys
- [x] 3-tier rate limiting (auth endpoints, inference endpoints, default)
- [x] PostgreSQL 16 with pgvector extension
- [x] Prisma ORM with 27 models and 19 enums (`db/schemas/schema.prisma`)
- [x] Request validation via Zod schemas on all routes
- [x] Health check endpoint (`/health`)
- [x] pino-http request logging

### Registry & Governance (COMPLETE)

Resource lifecycle management with Git-backed versioning and policy enforcement.

- [x] Resource registry with semver versioning and dependency resolution
- [x] Git sync (bidirectional sync between registry and Git repositories)
- [x] Marketplace with browse, search, install, and fork workflows
- [x] Review system (star ratings, text reviews per artifact)
- [x] Approval workflows (submit, review, approve/reject state machine)
- [x] Policy engine (configurable rules evaluated at deploy/publish time)
- [x] Audit logging (immutable log of all governance actions)

### Model Gateway (COMPLETE)

Centralized LLM routing with cost controls and safety guardrails.

- [x] Multi-provider LLM routing across 18 providers
- [x] Model catalog with 30+ models including pricing, context windows, and capabilities
- [x] Model router service (provider selection, fallback chains, load balancing)
- [x] Guardrails engine: PII detection/redaction, content filtering, toxicity scoring, custom rules
- [x] Rate limiting per user, team, model, and global tiers
- [x] Cost event tracking (per-request token counts and dollar costs)
- [x] Budget management (per-team/project budgets with alerts)
- [x] Cost forecasting (trend-based projection)
- [x] Inference capture (buffered logging of all LLM requests/responses)
- [x] S3 export of inference logs for offline analysis

### Agent Runtimes (COMPLETE)

Three shared runtimes that serve any agent from YAML configuration.

**TypeScript Runtime** (`agent-runtime/`):
- [x] Mastra + Vercel AI SDK foundation
- [x] Config loader with 5-layer merge hierarchy (@global, @global.env, agent, agent.env, agent.local)
- [x] `+` (append list) and `^` (replace dict) merge prefixes
- [x] Agent factory: dynamic wiring of model, tools, memory, prompt
- [x] Model factory: Anthropic, OpenAI, Google, Databricks, Gateway providers
- [x] Generate options: temperature, top_p, top_k, max_tokens, stop_sequences, thinking, seed
- [x] System prompt combining: `system_prompt_ref` (file) + `system_prompt` (inline)
- [x] Hot-reload via file watching (config change detection without restart)
- [x] Retry with exponential backoff + jitter
- [x] Fallback model support (automatic failover to secondary model)
- [x] Input/output guardrails (content_policy, pii_redaction, token_limit, custom)
- [x] Memory integration: 5 types (buffer_window, buffer, summary, entity, vector_store) x 3 backends (in_memory, redis, postgresql)
- [x] Vector search factory: Databricks REST API + Elasticsearch (kNN, hybrid)
- [x] Auto-generated `search_{index_name}` tools from YAML `vector_search_indexes`
- [x] Subagent delegation via HTTP (`subagents:` in YAML creates call tools)
- [x] MCP tool discovery and execution (JSON-RPC 2.0)
- [x] Streaming SSE (`/invocations/stream`)
- [x] Dockerfile: single image serves all TypeScript agents

**Python Runtime** (`agent-runtime-python/`):
- [x] FastAPI + LangChain/LangGraph foundation
- [x] Framework-pluggable agent factory (langchain, langgraph, deepagents, crewai, openai_agents, google_adk, strands, pydantic_ai, autogen, custom)
- [x] Model class override via dynamic import (`model_class` FQN)
- [x] 8 model providers (Anthropic, OpenAI, Google, Databricks, Gateway, Bedrock, Azure, LiteLLM)
- [x] Generic per-request auth context (`AuthContext` protocol with pluggable providers)
- [x] HITL interrupt + dedup cache (`HumanInTheLoopManager`)
- [x] Tool-level `requires_approval` support
- [x] User-isolated memory (namespace pattern: agent_name + user_id)
- [x] Semantic memory search with pluggable embeddings
- [x] Environment variable injection from YAML config
- [x] Same 5-layer config merge, hot-reload, streaming, vector search as TypeScript runtime

**Kotlin Runtime** (`agent-runtime-kotlin/`):
- [x] Ktor + Koog foundation
- [x] Config loader, agent factory, model factory, routes
- [x] Gradle build with shadow JAR (eclipse-temurin:21-jre)
- [x] Same config merge hierarchy and YAML schema support

### Tool Ecosystem (COMPLETE)

Pre-built tools, MCP servers, and SDK templates for rapid agent development.

**uap-toolkit** (83+ tools in 22 modules):
- [x] `zendesk` (1 tool) — Help article search
- [x] `course_catalog` (2 tools) — Course search
- [x] `featurestore` (2 tools) — Feature store queries
- [x] `learner_state` (2 tools) — Learner progress
- [x] `learner_state_agent` (1 tool) — Learner state agent call
- [x] `learner_profile` (2 tools) — Learner profiles
- [x] `goal_elicitation` (2 tools) — Goal elicitation
- [x] `tutor` (1 tool) — Tutoring
- [x] `s3_persist` (2 tools) — S3 persistence
- [x] `execute_query` (1 tool) — SQL execution
- [x] `onboarding` (1 tool) — Onboarding
- [x] `lecture_lo` (2 tools) — Lecture learning objectives
- [x] `inline` (2 tools) — Calculator + echo (no MCP)
- [x] `memory` (3 tools) — Conversation memory (store/retrieve/search)
- [x] `databricks.query` (2 tools) — Submit + retrieve SQL queries
- [x] `databricks.user` (1 tool) — Current user info
- [x] `databricks.lineage` (2 tools) — Table + column lineage
- [x] `databricks.job` (4 tools) — Job listing, runs, details
- [x] `atlassian` (4 tools) — Jira issues + Confluence wiki
- [x] `airflow.dag` (9 tools) — DAG ops via Lambda proxy
- [x] `common` (2 tools) — Sleep + echo
- [x] `taxonomy` (1 tool) — Save topic recommendation
- [x] `cip.content_quality` (10 tools) — Quality assessment (8-dimension scoring)

**MCP Servers** (13 servers, ports 9100-9112):
- [x] Zendesk, Course Catalog, Featurestore, Learner State, Learner Profile
- [x] Goal Elicitation, Tutor, S3 Persist, Execute Query, Onboarding
- [x] Lecture LO, Learner State Agent, additional servers

**SDK Templates** (16 templates):
- [x] Python (9): langchain, langgraph, crewai, openai-agents, claude-sdk, google-adk, strands, pydantic-ai, autogen
- [x] TypeScript (6): mastra, langchain, langgraph, openai-agents, claude-sdk, google-adk
- [x] Kotlin (1): koog

### Agents (COMPLETE)

22 production agents and 8 examples covering support, learning, content intelligence, and data platform domains.

**Production Agents (22):**
- [x] Support domain: support-agent, featurestore-agent, course-personalization-agent, learner-profile-builder-agent
- [x] Microlearning domain (6): goal-elicitation, planner, course, guided-learning-tutor, widget-generator, content-analyzer-lecture, plus lightweight-supervisor and curriculum-builder
- [x] Streaming: streaming-agent (inline tools), streaming-supervisor-agent (multi-agent)
- [x] Education: educational-search-agent, transcript-segmentation-lecture
- [x] Learner state: learner-state-agent (AIMAS/gpt-4.1)
- [x] DIP/Content Intelligence: cip-taxonomy-agent, cip-content-quality-agent (Databricks model + vector search)
- [x] Data Platform: dp-support-agent (26 tools, Atlassian+Airflow+Databricks), lineage-agent, platform-cost-advisor-agent

**Example Agents (8):**
- [x] Low-code examples: example-agent, example-supervisor-agent, a2a-calculator-agent, a2a-converter-agent, a2a-orchestrator-agent, openai-with-aimas
- [x] Full-code examples: mastra-code-agent (custom tools), mastra-rag-agent (vector search + memory)

### UI — React SPA (COMPLETE)

Vite + React 19 single-page application with 13 feature areas.

**Agent Builder (4 modes):**
- [x] Visual mode: ReactFlow graph with 10 node types (Agent, Model, Prompt, Tool, Subagent, Memory, RAG, MCP, A2A, Guardrail)
- [x] YAML mode: Monaco editor with DIP schema completions, insert snippets, validation markers
- [x] Prompt mode: Markdown editor for `prompt.md` with live preview
- [x] IDE mode: 14 code generators (8 Python + 6 TypeScript), framework/language selector, sandbox execution, AI assistant, ZIP export
- [x] ModelPicker from model catalog (searchable, grouped by provider)
- [x] MCPServerPicker (13 registered servers with port/description)
- [x] ToolkitPicker (83 tools across 22 modules)
- [x] RAG panel (Databricks + Elasticsearch configuration)
- [x] Guardrails panel (input/output, 5 types, 3 actions)
- [x] Advanced model params (top_p, top_k, thinking, retry, fallback, timeout)
- [x] Execution controls (tool_choice, parallel_tool_calls, max_iterations, max_execution_time)
- [x] Undo/redo (50-entry stacks)
- [x] Version history, template gallery, import/export
- [x] New Agent dialog with 3-tier selection (No-Code, Low-Code, Full Code)
- [x] Filesystem CRUD (GET/PUT/DELETE `/api/v1/agents/filesystem/:name`)

**Platform Pages:**
- [x] Chat interface with assistant-ui integration (classic + enhanced mode toggle)
- [x] Tool call visualization (expandable ToolCallFallback with input/output)
- [x] Control center dashboard
- [x] Monitoring pages (health, metrics, traces, alerts)
- [x] Cost tracking dashboard (events, budgets, forecasting)
- [x] Governance pages (approvals, policies, audit log)
- [x] Deployment management
- [x] Model gateway management (catalog, guardrails, rate limits)
- [x] Registry browser
- [x] Marketplace

**Test Coverage:**
- [x] 770 UI unit tests (Testing Library + jsdom)

### Deployment Infrastructure (COMPLETE)

Production-grade deployment across multiple cloud targets.

- [x] Docker Compose: 30 services (unified app, agents, MCP servers, PostgreSQL, Redis, Prometheus)
- [x] Helm chart (`deploy/helm/unified-agent-platform/`) based on nodejs-app-chart
- [x] ArgoCD Application manifests for 3 regions
- [x] Terraform modules: EKS, GKE, RDS, S3
- [x] GitHub Actions CI/CD pipelines
- [x] Observability stack: Prometheus scraping, Grafana dashboards, OpenTelemetry Collector

### Testing (COMPLETE)

Comprehensive test suite with enforced coverage thresholds.

- [x] 2891 backend unit tests (Vitest 2.1, v8 coverage)
- [x] 61 integration tests (cross-module)
- [x] 770 UI unit tests (Testing Library + jsdom)
- [x] E2E tests (Playwright): chat, cost dashboard, deployments, governance, monitoring, settings
- [x] 80% coverage thresholds enforced (statements, branches, functions, lines)
- [x] Forks pool for isolation, 10-second timeout
- [x] Prisma mock pattern, logger mock pattern, pino-http mock pattern

---

## Phase 1: Production Hardening (PLANNED)

**Goal:** Close the remaining gaps between "demo-ready" and "production-ready" for the chat experience and agent execution lifecycle.

**Items:**

- [ ] HITL approval UI in chat (approve/reject/cancel buttons rendered inline on tool call cards)
- [ ] HITL state machine: pending → approved/rejected/cancelled with timeout (configurable per tool)
- [ ] HITL dedup: prevent duplicate tool executions when user retries or reconnects
- [ ] Conversation thread management: create new thread, switch between threads, delete threads
- [ ] Thread persistence: store threads in PostgreSQL with user ownership
- [ ] URL-based thread state (`?thread={id}`) for shareable conversation links
- [ ] Memory display panel in chat sidebar (view saved memories, search, delete)
- [ ] Terminal panel for sandbox execution output (xterm.js embedded in IDE mode)
- [ ] Response persistence: buffer partial streamed responses server-side
- [ ] Stream recovery on disconnect: resume from last received token on reconnect
- [ ] Structured output rendering: when agent declares `output_schema`, render JSON as a form/table
- [ ] Error recovery UX: retry failed tool calls, show meaningful error messages
- [ ] Agent status indicators: connecting, streaming, tool-calling, waiting-for-approval, error

**Dependencies:** None (builds on existing COMPLETE infrastructure).

---

## Phase 2: Agent Evaluation & Quality (PLANNED)

**Goal:** Provide automated quality measurement so teams can ship agents with confidence and catch regressions before users do.

**Items:**

- [ ] Offline evaluation runner CLI (`uap eval <agent-name>`)
- [ ] Evaluation dataset format: JSON lines with `input`, `expected_output`, `expected_tool_calls`, `tags`
- [ ] Golden test set management: CRUD API for datasets per agent (`/api/v1/eval/datasets`)
- [ ] Dataset editor UI: upload, edit, tag, version evaluation datasets
- [ ] Judge model integration: auto-grade responses using a configurable judge LLM
- [ ] Evaluation metrics: correctness, relevance, groundedness, tool accuracy, latency
- [ ] Custom metric plugins: user-defined scoring functions (Python or TypeScript)
- [ ] Evaluation run history: store results in PostgreSQL, display trends in UI
- [ ] Regression detection: compare current run against baseline, alert on score drops > threshold
- [ ] Evaluation reports: exportable HTML/PDF summaries per run
- [ ] A/B testing framework: deploy two agent versions, split traffic, compare metrics
- [ ] Canary deployments: route N% of traffic to new version, auto-rollback on quality drop
- [ ] Integration with CI/CD: run evaluations on PR, block merge if scores below threshold
- [ ] Prisma models: `EvaluationDataset`, `EvaluationRun`, `EvaluationResult`, `EvaluationMetric`

**Dependencies:** Phase 1 (conversation persistence needed for evaluation dataset capture from real conversations).

---

## Phase 3: Developer Experience (PLANNED)

**Goal:** Make the local development loop fast and frictionless — from scaffolding a new agent to testing it locally to deploying it.

**Items:**

- [ ] CLI tool package (`uap` binary, published to npm)
- [ ] `uap create agent --template <low-code|full-code> --runtime <ts|python|kotlin>` scaffolding
- [ ] `uap create tool --module <name>` tool scaffolding with contract stub
- [ ] `uap build <agent>` — validate YAML, resolve tools, produce deployable artifact
- [ ] `uap test <agent>` — run evaluation datasets locally
- [ ] `uap deploy <agent> --target <k8s|docker|databricks>` — deploy from CLI
- [ ] `uap eval <agent>` — run offline evaluation (from Phase 2)
- [ ] `uap logs <agent>` — tail agent logs from deployment target
- [ ] `uap chat <agent>` — interactive terminal chat session
- [ ] Local development server: hot-reload + automatic tool mocking for missing MCP servers
- [ ] Tool mock framework: record real tool responses, replay in tests
- [ ] VS Code extension: YAML schema validation, prompt.md preview, inline tool docs
- [ ] Interactive API documentation: auto-generated OpenAPI/Swagger spec from route definitions
- [ ] API playground in UI: test any endpoint with pre-filled auth tokens
- [ ] Agent debugging mode: verbose logging of config merge, tool resolution, prompt assembly

**Dependencies:** Phase 2 (eval command depends on evaluation runner).

---

## Phase 4: Enterprise Features (PLANNED)

**Goal:** Make UAP ready for large-scale enterprise deployment with multi-team isolation, compliance, and cost accountability.

**Items:**

- [ ] Multi-tenant resource isolation: team-scoped agents, tools, prompts, RAG collections
- [ ] Namespace enforcement: all resources prefixed with team identifier
- [ ] Network policies: agent-to-agent calls restricted by team boundaries (configurable)
- [ ] SSO integration: SAML 2.0 provider support
- [ ] SSO integration: OIDC provider support (beyond current OAuth2)
- [ ] Directory sync: auto-provision users/teams from identity provider
- [ ] Data residency controls: per-team region constraints for model routing and data storage
- [ ] Retention policies: auto-delete inference logs, conversations, and audit records after N days
- [ ] Data classification: tag resources with sensitivity levels (public, internal, confidential, restricted)
- [ ] SLA monitoring: per-agent latency P50/P95/P99 targets with alerting
- [ ] Availability tracking: uptime percentage per agent and per service
- [ ] Cost allocation: chargeback reports per team/project/agent
- [ ] Budget enforcement: hard limits that block requests when budget exhausted
- [ ] Usage quotas: per-team limits on agent count, tool count, deployment count
- [ ] Admin dashboard: cross-team view of resource usage, cost, and health
- [ ] Prisma models: `Tenant`, `TenantMembership`, `DataResidencyPolicy`, `RetentionPolicy`

**Dependencies:** None strictly, but Phase 1 (production hardening) should land first for stability.

---

## Phase 5: Advanced Agent Patterns (PLANNED)

**Goal:** Support complex agent architectures beyond simple request-response — workflows, long-running tasks, multi-modal processing, and multi-agent coordination.

**Items:**

- [ ] Workflow/DAG execution engine: define multi-step pipelines in YAML
- [ ] Step types: LLM call, tool call, conditional branch, parallel fan-out, human approval gate
- [ ] Workflow persistence: checkpoint state to PostgreSQL after each step
- [ ] Workflow resume: restart from last checkpoint on failure or process restart
- [ ] Workflow UI: visual DAG editor (extend existing ReactFlow canvas)
- [ ] Agent handoff protocol: OpenAI Agents SDK-style `transfer_to_agent` tool
- [ ] Handoff context passing: conversation history + metadata forwarded to target agent
- [ ] Consensus/voting pattern: fan-out to N agents, aggregate responses, pick best answer
- [ ] Voting strategies: majority, weighted, judge-model selection
- [ ] Long-running agents: support tasks spanning hours or days
- [ ] Checkpoint/resume: serialize agent state at tool call boundaries
- [ ] Progress reporting: SSE updates for long-running tasks (`/invocations/{id}/status`)
- [ ] Multi-modal input: image, audio, PDF upload in chat and API
- [ ] Multi-modal output: image generation, audio synthesis, chart rendering
- [ ] Multi-modal tools: tools that accept/return binary data (images, files)
- [ ] Agent composition: declarative multi-agent graphs in YAML (supervisor, chain, mesh)

**Dependencies:** Phase 1 (stream recovery and response persistence needed for long-running agents).

---

## Phase 6: Ecosystem & Integration (PLANNED)

**Goal:** Extend UAP beyond the internal platform into an ecosystem where agents, tools, and prompts can be shared, discovered, and triggered from external systems.

**Items:**

- [ ] Public marketplace: cross-organization sharing of agents, tools, and prompts
- [ ] Marketplace publishing workflow: review, approve, publish with versioning
- [ ] Marketplace billing: usage-based pricing for premium agents/tools
- [ ] Webhook/event system: emit events on agent lifecycle (deployed, invoked, failed, approved)
- [ ] Event subscriptions: register HTTP callbacks for specific event types
- [ ] Event log: queryable event history with filtering
- [ ] Third-party tool marketplace: community-contributed tool modules
- [ ] Tool certification: automated testing + manual review for marketplace tools
- [ ] Slack bot integration: invoke agents from Slack channels, receive responses as threads
- [ ] Microsoft Teams bot integration: same as Slack but via Bot Framework
- [ ] GitHub Copilot extension: invoke UAP agents as Copilot skills
- [ ] Zapier/Make integration: trigger agents from workflow automation platforms
- [ ] REST webhook trigger: invoke agents via incoming webhook URL
- [ ] Scheduled invocations: cron-based agent execution (e.g., daily report generation)
- [ ] Email trigger: invoke agents from incoming email (via SES/SendGrid)
- [ ] Agent embedding: JavaScript SDK to embed agent chat in external websites

**Dependencies:** Phase 4 (multi-tenant isolation needed for cross-org marketplace).

---

## Phase 7: Performance & Scale (PLANNED)

**Goal:** Scale UAP from tens to thousands of concurrent agents with predictable latency and cost.

**Items:**

- [ ] Connection pooling: PgBouncer sidecar for PostgreSQL connection management
- [ ] Redis Cluster support: replace single Redis with cluster for HA and throughput
- [ ] Redis Sentinel support: automatic failover for Redis
- [ ] Agent instance autoscaling: Horizontal Pod Autoscaler (HPA) based on request queue depth
- [ ] KEDA integration: scale-to-zero for idle agents, scale-from-zero on first request
- [ ] Model response caching: semantic dedup (cache responses for similar prompts)
- [ ] Cache invalidation: TTL-based + manual purge via API
- [ ] Batch inference mode: accept array of inputs, process in parallel, return array of outputs
- [ ] Request queuing: async job queue for non-interactive workloads (Redis Streams or SQS)
- [ ] Priority queues: high/medium/low priority lanes with weighted processing
- [ ] Database read replicas: route read queries to replicas, writes to primary
- [ ] Sharded storage: partition inference logs by date for faster queries
- [ ] CDN for static assets: serve UI bundle from CloudFront/Fastly
- [ ] gRPC transport option: for agent-to-agent calls in latency-sensitive paths
- [ ] Connection keep-alive tuning: optimize HTTP/2 multiplexing for agent runtimes
- [ ] Load testing harness: k6 scripts for agent endpoints with realistic payloads
- [ ] Performance benchmarks: tracked per release, regression alerts

**Dependencies:** Phase 4 (multi-tenant isolation affects connection pool and cache partitioning).

---

## Phase Summary

| Phase | Focus | Status | Key Dependency |
|-------|-------|--------|---------------|
| — | Core Platform, Runtimes, Tools, Agents, UI, Deploy, Tests | COMPLETE | — |
| 1 | Production Hardening | PLANNED | None |
| 2 | Agent Evaluation & Quality | PLANNED | Phase 1 |
| 3 | Developer Experience | PLANNED | Phase 2 |
| 4 | Enterprise Features | PLANNED | Phase 1 |
| 5 | Advanced Agent Patterns | PLANNED | Phase 1 |
| 6 | Ecosystem & Integration | PLANNED | Phase 4 |
| 7 | Performance & Scale | PLANNED | Phase 4 |

Phases 1 and 4 can run in parallel. Phases 2 and 5 can run in parallel once Phase 1 is done. Phase 3 depends on Phase 2. Phases 6 and 7 depend on Phase 4.

```
            ┌──── Phase 2 (Eval) ──── Phase 3 (DX)
            │
Phase 1 ────┤
(Hardening)  │
            └──── Phase 5 (Advanced Patterns)

Phase 4 ────┬──── Phase 6 (Ecosystem)
(Enterprise) │
            └──── Phase 7 (Scale)
```

---

## How to Recreate This Project From Scratch

If you were starting from zero, here is the build order. Each step produces a working, testable increment.

### Step 1: Foundation (Week 1-2)

Set up the monorepo skeleton and shared infrastructure.

1. Initialize Node.js monorepo with `package.json`, TypeScript config, ESLint, Prettier
2. Set up Vitest with `vitest.unified.config.ts` and `vitest.shared.ts` (80% coverage thresholds, forks pool)
3. Create `db/schemas/schema.prisma` with PostgreSQL provider and pgvector extension
4. Define core Prisma models: `User`, `Team`, `TeamMembership`, `ApiKey`, `Session`
5. Create `src/shared/prisma.ts` (single PrismaClient), `src/shared/redis.ts` (Redis factory), `src/shared/logger.ts` (pino)
6. Create `src/app.ts` (Express factory) and `src/server.ts` (HTTP entry point on port 8080)
7. Add health check route (`/health`)
8. Write Docker Compose with PostgreSQL 16 + Redis 7
9. Write Dockerfile for the unified app

### Step 2: Auth & Middleware (Week 2-3)

Secure the platform before adding any features.

1. Create `src/middleware/auth.ts` — JWT validation middleware
2. Create `src/middleware/rate-limit.ts` — 3-tier rate limiting (Redis-backed sliding window)
3. Build `src/platform/auth/` — OAuth2 flows (Databricks, GitHub, Google), JWT issuance, refresh tokens
4. Add RBAC: roles table, team membership, permission checking middleware
5. Add API key management: create, revoke, scope to teams
6. Add Prisma models: `Role`, `Permission`, `OAuthToken`, `AuditLog`
7. Write tests: mock Prisma, test each auth flow, test rate limit tiers

### Step 3: Registry & Model Gateway (Week 3-5)

The two platform services that everything else depends on.

1. Build `src/platform/registry/` — CRUD for resources (agents, tools, prompts, RAG collections)
2. Add semver versioning, dependency resolution, Git sync service
3. Add Prisma models: `Resource`, `ResourceVersion`, `ResourceDependency`
4. Build `src/platform/model-gateway/` — provider abstraction, model catalog, routing logic
5. Add guardrails engine: PII regex scanner, content filter, toxicity scorer, custom rule evaluator
6. Add rate limiting per user/team/model/global
7. Add Prisma models: `ModelProvider`, `ModelConfig`, `GuardrailRule`, `RateLimit`
8. Write tests for both modules (route tests with supertest, service unit tests)

### Step 4: Agent YAML Schema & Config System (Week 5-6)

Define the configuration format that all runtimes will consume.

1. Create `agents/@global/agent.yaml` with sensible defaults (model, memory, streaming)
2. Define the full YAML schema in TypeScript (`agent-runtime/src/config-schema.ts`) and Zod
3. Implement 5-layer config merge: @global → @global.env → agent → agent.env → agent.local
4. Implement `+` (append) and `^` (replace) merge prefixes
5. Create 2-3 example agent directories: `agents/example-agent/agent.yaml` + `prompt.md`
6. Write config loader tests covering merge order, prefixes, missing files

### Step 5: TypeScript Agent Runtime (Week 6-8)

The primary runtime — proves the YAML-driven architecture works.

1. Create `agent-runtime/` with Mastra + Vercel AI SDK
2. Build config loader (reads YAML, applies merge, validates schema)
3. Build model factory (provider → SDK client mapping for Anthropic, OpenAI, Google, Databricks)
4. Build agent factory (wires model + tools + memory + prompt into Mastra agent)
5. Build generate options (temperature, top_p, thinking, etc. applied at generate time)
6. Build routes: `POST /invocations` (sync), `POST /invocations/stream` (SSE)
7. Add memory integration: buffer_window, buffer, summary with in_memory and Redis backends
8. Add vector search factory: Databricks REST API + Elasticsearch
9. Add subagent delegation: `subagents:` YAML entries create HTTP call tools
10. Add MCP tool discovery: connect to MCP servers, list tools, proxy calls
11. Add hot-reload: watch agent YAML + prompt.md, rebuild agent on change
12. Write Dockerfile: single image, `AGENT_NAME` env var selects which agent to serve

### Step 6: Tool Ecosystem (Week 8-10)

Build the tools that agents actually use.

1. Create `uap-toolkit/` with dotted-path registry (`uap_toolkit.module.tool_name`)
2. Implement tool contract pattern: `ToolContract<TInput, TOutput>` with Zod schemas
3. Build first MCP server (e.g., Zendesk) on port 9100
4. Build toolkit wrapper that calls MCP server tools
5. Add inline tools (no MCP dependency) for calculator, echo, etc.
6. Build remaining MCP servers (course_catalog, featurestore, etc.) on ports 9101-9112
7. Build remaining toolkit modules (databricks, atlassian, airflow, etc.)
8. Support nested namespaces: `uap_toolkit.databricks.query.submit_query`
9. Write `shared/tool-contracts/` for cross-package type safety

### Step 7: Python & Kotlin Runtimes (Week 10-12)

Replicate the TypeScript runtime's capabilities in Python and Kotlin.

1. Create `agent-runtime-python/` with FastAPI + LangChain
2. Port config loader, model factory, agent factory, routes
3. Add framework dispatch: langchain, langgraph, crewai, etc.
4. Add Python-specific features: `model_class` dynamic import, `AuthContext` protocol
5. Add HITL manager with interrupt + dedup
6. Create `agent-runtime-kotlin/` with Ktor + Koog
7. Port config loader, model factory, agent factory, routes
8. Write Dockerfiles for both runtimes
9. Ensure all three runtimes pass the same agent YAML integration tests

### Step 8: Production Agents (Week 12-14)

Build the actual agents that deliver business value.

1. Create support-agent, featurestore-agent, course-personalization-agent
2. Create microlearning agents (goal-elicitation, planner, course, tutor, widget-generator, supervisor)
3. Create streaming-agent with inline tools, streaming-supervisor-agent
4. Create DIP agents: cip-taxonomy-agent, cip-content-quality-agent, dp-support-agent, lineage-agent, platform-cost-advisor-agent
5. Create example agents for each tier (low-code, full-code, A2A, supervisor)
6. Write integration tests for each agent's tool resolution and config loading

### Step 9: Builders & Governance (Week 14-16)

The six builder modules and governance layer.

1. Build `src/builders/agent-builder/` — YAML generation, code generation (14 generators), Git sync
2. Build `src/builders/prompt-builder/` — prompt CRUD, versioning, A/B testing, Git sync
3. Build `src/builders/tool-builder/` — tool CRUD, dependency resolution, sandbox execution, Git sync
4. Build `src/builders/rag-builder/` — vector collection management, semantic search
5. Build `src/builders/memory-builder/` — conversation memory CRUD
6. Build `src/builders/marketplace/` — browse, install, fork, review workflows
7. Build `src/platform/governance/` — approval state machine, policy engine, audit log
8. Build `src/platform/cost-tracker/` — cost events, budgets, forecasting
9. Build `src/platform/monitoring/` — health checks, metrics, traces, alerts
10. Build `src/platform/inference-capture/` — inference buffering, S3 export
11. Build `src/runtime/sandbox/` — Docker-based code execution
12. Build `src/runtime/a2a-server/` — Agent-to-Agent JSON-RPC 2.0 protocol
13. Build `src/runtime/mcp-server/` — MCP server registry and management
14. Build `src/runtime/deployer/` — multi-target deployment (Kubernetes, Fargate, Cloud Run, Azure Container Apps, Bedrock, OKE)

### Step 10: UI (Week 16-20)

Build the React SPA with all 13 feature areas.

1. Set up Vite + React 19 + TypeScript + Tailwind CSS in `ui/`
2. Build app shell: sidebar navigation, topbar, theme toggle
3. Build agent builder with 4 modes:
   - Visual: ReactFlow canvas with 10 node types, Add Node palette, edge labels, validation badges
   - YAML: Monaco editor with schema completions, insert snippets
   - Prompt: Markdown editor with live preview
   - IDE: code generation, sandbox execution, AI assistant, ZIP export
4. Build component pickers: ModelPicker, MCPServerPicker, ToolkitPicker
5. Build property panels: RAG, Guardrails, Memory, Agent execution controls
6. Build chat interface with assistant-ui (ExternalStoreRuntime adapter, SSE streaming, tool call visualization)
7. Build control center dashboard
8. Build monitoring pages (health, metrics, traces, alerts)
9. Build cost tracking pages (events, budgets, forecasts)
10. Build governance pages (approvals, policies, audit log)
11. Build deployment management pages
12. Build model gateway management pages
13. Build registry and marketplace pages
14. Build template gallery with tier-aware New Agent dialog
15. Add undo/redo, version history, import/export
16. Write 770+ UI unit tests

### Step 11: SDK Templates (Week 20-21)

Provide starter projects for every supported framework.

1. Create Python templates (9): langchain, langgraph, crewai, openai-agents, claude-sdk, google-adk, strands, pydantic-ai, autogen
2. Create TypeScript templates (6): mastra, langchain, langgraph, openai-agents, claude-sdk, google-adk
3. Create Kotlin template (1): koog
4. Each template includes: project scaffold, Dockerfile, README, example agent YAML, test file

### Step 12: Deployment Infrastructure (Week 21-23)

Make it production-deployable on any cloud.

1. Write Docker Compose for full local stack (30 services)
2. Create Helm chart (`deploy/helm/unified-agent-platform/`)
3. Write Terraform modules: EKS cluster, GKE cluster, RDS PostgreSQL, S3 buckets
4. Create ArgoCD Application manifests for 3 regions
5. Write GitHub Actions workflows: build, test, deploy
6. Configure observability: Prometheus scrape configs, Grafana dashboards, OTel Collector

### Step 13: Testing & Hardening (Week 23-24)

Fill coverage gaps and harden for production.

1. Write backend unit tests to reach 80% coverage across all modules
2. Write integration tests for cross-module flows (auth → registry → deploy)
3. Write E2E tests with Playwright (chat, deployments, governance, monitoring)
4. Set up coverage enforcement in CI (fail build below 80%)
5. Load test critical paths (model gateway, agent invocations)

---

## Estimated Total: 24 weeks for COMPLETE features, then ongoing phases

The 7 planned phases would add approximately:
- Phase 1 (Production Hardening): 4-6 weeks
- Phase 2 (Evaluation): 6-8 weeks
- Phase 3 (Developer Experience): 6-8 weeks
- Phase 4 (Enterprise): 8-10 weeks
- Phase 5 (Advanced Patterns): 8-12 weeks
- Phase 6 (Ecosystem): 10-12 weeks
- Phase 7 (Performance): 6-8 weeks

Phases can overlap based on team capacity. The dependency graph above determines sequencing constraints.
