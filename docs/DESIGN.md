# DESIGN.md — Udemy Agent Platform

Detailed design reference covering API contracts, database schema, agent configuration format, tool system, UI pages, authentication, and deployment targets.

For architecture overview, see [ARCHITECTURE.md](ARCHITECTURE.md). For development patterns, see [DEVELOPMENT.md](DEVELOPMENT.md).

---

## Table of Contents

1. [API Reference](#1-api-reference)
2. [Database Schema](#2-database-schema)
3. [Agent Configuration Format](#3-agent-configuration-format)
4. [Model Provider Reference](#4-model-provider-reference)
5. [Tool System](#5-tool-system)
6. [UI Pages Reference](#6-ui-pages-reference)
7. [Authentication & Authorization](#7-authentication--authorization)
8. [Deployment Targets](#8-deployment-targets)

---

## 1. API Reference

All platform routes are served on port 8080 under the `/api/v1` prefix. Agent runtime routes are served per-agent on ports 9200-9250.

### 1.1 Platform — Registry

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/registry` | Create registry entry | `{ resourceType, name, version, description, language, framework, tags, configYaml, metadata }` | `{ id, ...entry }` |
| GET | `/api/v1/registry` | List entries (paginated, filterable) | Query: `?type=AGENT&framework=MASTRA&page=1&limit=20` | `{ items[], total, page }` |
| PUT | `/api/v1/registry/:id` | Update entry | Same as POST | `{ id, ...entry }` |
| DELETE | `/api/v1/registry/:id` | Delete entry | — | `{ success: true }` |
| GET | `/api/v1/registry/ref/:type/:name/:version` | Resolve by type/name/version | — | `{ id, ...entry }` |
| GET | `/api/v1/git/sync` | Sync registry from Git | Query: `?repo=&path=` | `{ synced: number }` |
| GET | `/api/v1/git/status` | Git sync status | — | `{ lastSync, entries[] }` |

### 1.2 Platform — Auth & RBAC

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/v1/auth/login/:provider` | Initiate OAuth2 flow | — | Redirect to provider |
| GET | `/api/v1/auth/callback/:provider` | OAuth2 callback | Query: `?code=&state=` | `{ accessToken, refreshToken, user }` |
| POST | `/api/v1/auth/exchange` | Exchange auth code for tokens | `{ code, provider }` | `{ accessToken, refreshToken }` |
| POST | `/api/v1/auth/refresh` | Refresh access token | `{ refreshToken }` | `{ accessToken, refreshToken }` |
| GET | `/api/v1/users` | List users | Query: `?email=&page=&limit=` | `{ items[], total }` |
| POST | `/api/v1/users` | Create user | `{ email, name, provider, providerId }` | `{ id, ...user }` |
| POST | `/api/v1/users/:id/roles` | Assign role to user | `{ roleId, scope, scopeId? }` | `{ id, ...userRole }` |
| GET | `/api/v1/teams` | List teams | — | `{ items[] }` |
| POST | `/api/v1/teams` | Create team | `{ name, description? }` | `{ id, ...team }` |
| POST | `/api/v1/api-keys` | Create API key | `{ name, scopes[], expiresAt? }` | `{ id, key, ...apiKey }` |
| DELETE | `/api/v1/api-keys/:id` | Revoke API key | — | `{ success: true }` |

### 1.3 Platform — Model Gateway

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/models/invoke` | Synchronous LLM invocation | `{ model, messages[], temperature?, max_tokens? }` | `{ id, content, usage }` |
| POST | `/api/v1/models/invoke/stream` | Streaming LLM invocation (SSE) | Same as invoke | SSE stream: `data: { delta, ... }` |
| POST | `/api/v1/models/embed` | Generate embeddings | `{ model, input: string[] }` | `{ embeddings: number[][] }` |
| GET | `/api/v1/models` | List registered models | Query: `?provider=&type=&active=` | `{ items[] }` |
| GET | `/api/v1/models/catalog` | Available model catalog | — | `{ providers: { models[] }[] }` |
| POST | `/api/v1/rate-limits` | Create rate limit | `{ modelId, scope, requestsPerMinute, tokensPerMinute }` | `{ id, ...rateLimit }` |
| GET | `/api/v1/rate-limits` | List rate limits | Query: `?modelId=` | `{ items[] }` |
| PUT | `/api/v1/rate-limits/:id` | Update rate limit | Same as POST | `{ id, ...rateLimit }` |
| POST | `/api/v1/guardrails` | Create guardrail | `{ name, type, params, action }` | `{ id, ...guardrail }` |
| GET | `/api/v1/guardrails` | List guardrails | — | `{ items[] }` |
| PUT | `/api/v1/guardrails/:id` | Update guardrail | Same as POST | `{ id, ...guardrail }` |
| POST | `/api/v1/guardrails/test` | Test guardrail against input | `{ guardrailId, input }` | `{ passed, violations[] }` |

### 1.4 Platform — Governance

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/approvals` | Create approval request | `{ resourceType, resourceId, action, reason? }` | `{ id, ...request }` |
| GET | `/api/v1/approvals` | List approval requests | Query: `?status=PENDING&resourceType=` | `{ items[] }` |
| POST | `/api/v1/approvals/:id/approve` | Approve request | `{ comment? }` | `{ id, status: "APPROVED" }` |
| POST | `/api/v1/approvals/:id/reject` | Reject request | `{ comment? }` | `{ id, status: "REJECTED" }` |
| POST | `/api/v1/approvals/:id/cancel` | Cancel request | — | `{ id, status: "CANCELED" }` |
| GET | `/api/v1/policies` | List policies | Query: `?resourceType=&active=` | `{ items[] }` |
| POST | `/api/v1/policies` | Create policy | `{ name, resourceType, conditions, actions }` | `{ id, ...policy }` |
| GET | `/api/v1/audit` | Query audit log | Query: `?userId=&action=&resourceType=&from=&to=` | `{ items[], total }` |

### 1.5 Platform — Monitoring

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/v1/health` | Platform health overview | — | `{ services: { name, status }[] }` |
| GET | `/api/v1/health/:service` | Individual service health | — | `{ status, latency, details }` |
| GET | `/api/v1/metrics` | Prometheus-format metrics | — | Text (Prometheus exposition format) |
| POST | `/api/v1/traces` | Submit trace spans | `{ spans: { traceId, spanId, ... }[] }` | `{ accepted: number }` |
| GET | `/api/v1/traces` | Query traces | Query: `?traceId=&service=&from=&to=` | `{ items[] }` |
| POST | `/api/v1/alerts` | Create alert rule | `{ name, condition, threshold, channels[] }` | `{ id, ...alert }` |
| GET | `/api/v1/alerts` | List alert rules | — | `{ items[] }` |

### 1.6 Platform — Cost Tracker

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/costs/record` | Record cost event | `{ agentId?, modelId?, tokensIn, tokensOut, costUsd }` | `{ id }` |
| GET | `/api/v1/costs/summary` | Cost summary | Query: `?period=7d&groupBy=agent` | `{ total, items[] }` |
| GET | `/api/v1/costs/breakdown` | Detailed cost breakdown | Query: `?from=&to=&agentId=&modelId=` | `{ items[] }` |
| POST | `/api/v1/budgets` | Create budget | `{ name, teamId, monthlyLimit, alertThresholds }` | `{ id, ...budget }` |
| GET | `/api/v1/budgets` | List budgets | Query: `?teamId=` | `{ items[] }` |
| PUT | `/api/v1/budgets/:id` | Update budget | Same as POST | `{ id, ...budget }` |

### 1.7 Platform — Inference Capture

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/inference/capture` | Capture inference record | `{ agentId?, modelId?, input, output, tokensIn, tokensOut, latencyMs }` | `{ id }` |
| GET | `/api/v1/inference/query` | Query inference records | Query: `?agentId=&modelId=&from=&to=&page=&limit=` | `{ items[], total }` |
| GET | `/api/v1/inference/stats` | Aggregate inference stats | Query: `?period=24h&groupBy=model` | `{ stats[] }` |
| POST | `/api/v1/inference/export` | Export records to S3 | `{ from, to, format? }` | `{ exportId, status }` |

### 1.8 Builders — Agent Builder

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/agents` | Create agent | `{ name, version, description, language, framework, configYaml }` | `{ id, ...agent }` |
| GET | `/api/v1/agents` | List agents | Query: `?framework=&language=&page=&limit=` | `{ items[], total }` |
| PUT | `/api/v1/agents/:id` | Update agent | Same as POST | `{ id, ...agent }` |
| DELETE | `/api/v1/agents/:id` | Delete agent | — | `{ success: true }` |
| POST | `/api/v1/agents/:id/generate` | Generate code from YAML | `{ language, framework }` | `{ files: { path, content }[] }` |
| POST | `/api/v1/agents/:id/validate` | Validate agent config | — | `{ valid, errors[] }` |
| POST | `/api/v1/agents/:id/test` | Run agent test | `{ input, conversationId? }` | `{ output, toolCalls[], latencyMs }` |
| POST | `/api/v1/agents/:id/sync` | Sync agent to Git | `{ repo, path?, message? }` | `{ sha, url }` |
| GET | `/api/v1/templates` | List agent templates | Query: `?category=&language=` | `{ items[] }` |
| GET | `/api/v1/toolkit/tools` | List available toolkit tools | Query: `?namespace=` | `{ tools: { path, description }[] }` |
| PUT | `/api/v1/agents/filesystem/:name` | Write agent YAML + prompt to filesystem | `{ yaml, promptMarkdown? }` | `{ success: true }` |
| GET | `/api/v1/agents/filesystem/:name` | Read agent files from filesystem | — | `{ yaml, promptMarkdown? }` |
| DELETE | `/api/v1/agents/filesystem/:name` | Delete agent directory | — | `{ success: true }` |

### 1.9 Builders — Prompt Builder

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/prompts` | Create prompt | `{ name, content, variables[], tags[] }` | `{ id, ...prompt }` |
| GET | `/api/v1/prompts` | List prompts | Query: `?search=&tags=&page=&limit=` | `{ items[], total }` |
| PUT | `/api/v1/prompts/:id` | Update prompt (creates version) | Same as POST | `{ id, version, ...prompt }` |
| DELETE | `/api/v1/prompts/:id` | Delete prompt | — | `{ success: true }` |
| POST | `/api/v1/prompts/search` | Semantic prompt search | `{ query, limit? }` | `{ items[] }` |
| GET | `/api/v1/prompts/:id/versions` | List prompt versions | — | `{ versions[] }` |
| POST | `/api/v1/prompts/:id/test` | Test prompt with variables | `{ variables: Record<string,string>, model? }` | `{ output, latencyMs }` |

### 1.10 Builders — Tool Builder

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/tools` | Create tool | `{ name, description, inputSchema, code, language }` | `{ id, ...tool }` |
| GET | `/api/v1/tools` | List tools | Query: `?language=&page=&limit=` | `{ items[], total }` |
| PUT | `/api/v1/tools/:id` | Update tool | Same as POST | `{ id, ...tool }` |
| DELETE | `/api/v1/tools/:id` | Delete tool | — | `{ success: true }` |
| POST | `/api/v1/tools/search` | Search tools | `{ query, limit? }` | `{ items[] }` |
| POST | `/api/v1/tools/:id/execute` | Execute tool in sandbox | `{ input }` | `{ output, logs[], latencyMs }` |
| POST | `/api/v1/tools/:id/test` | Run tool tests | — | `{ passed, failed, results[] }` |
| POST | `/api/v1/tools/:id/validate` | Validate tool schema | — | `{ valid, errors[] }` |
| POST | `/api/v1/tools/:id/push` | Push tool to Git | `{ repo, message? }` | `{ sha }` |
| POST | `/api/v1/tools/:id/pull` | Pull tool from Git | `{ repo, path }` | `{ id, ...tool }` |

### 1.11 Builders — RAG Builder

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/vector-collections` | Create collection | `{ name, provider, embeddingModel, dimensions, metric?, chunkingConfig? }` | `{ id, ...collection }` |
| GET | `/api/v1/vector-collections` | List collections | Query: `?provider=&status=` | `{ items[] }` |
| PUT | `/api/v1/vector-collections/:id` | Update collection | Same as POST | `{ id, ...collection }` |
| DELETE | `/api/v1/vector-collections/:id` | Delete collection | — | `{ success: true }` |
| POST | `/api/v1/vector-collections/search` | Search across collections | `{ query, collections[], limit? }` | `{ results[] }` |
| POST | `/api/v1/vector-collections/:id/ingest` | Ingest documents | `{ documents: { content, metadata }[] }` | `{ ingested: number }` |
| POST | `/api/v1/vector-collections/:id/query` | Query single collection | `{ query, limit?, filters? }` | `{ results[] }` |

### 1.12 Builders — Memory Builder

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/memory-configs` | Create memory config | `{ name, shortTermProvider, shortTermConfig, longTermProvider, longTermConfig }` | `{ id, ...config }` |
| GET | `/api/v1/memory-configs` | List memory configs | — | `{ items[] }` |
| PUT | `/api/v1/memory-configs/:id` | Update memory config | Same as POST | `{ id, ...config }` |
| DELETE | `/api/v1/memory-configs/:id` | Delete memory config | — | `{ success: true }` |
| POST | `/api/v1/conversations` | Create conversation | `{ agentId, metadata? }` | `{ id, ...conversation }` |
| GET | `/api/v1/conversations` | List conversations | Query: `?agentId=&userId=` | `{ items[] }` |
| POST | `/api/v1/memory/store` | Store memory entry | `{ conversationId, role, content, metadata? }` | `{ id }` |
| POST | `/api/v1/memory/recall` | Recall conversation history | `{ conversationId, limit? }` | `{ messages[] }` |
| POST | `/api/v1/memory/search` | Semantic memory search | `{ query, agentId?, limit? }` | `{ results[] }` |
| POST | `/api/v1/memory/clear` | Clear conversation memory | `{ conversationId }` | `{ success: true }` |

### 1.13 Builders — Marketplace

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/v1/marketplace` | Browse marketplace | Query: `?type=&category=&search=&sort=&page=&limit=` | `{ items[], total }` |
| GET | `/api/v1/marketplace/featured` | Featured items | — | `{ items[] }` |
| GET | `/api/v1/marketplace/categories` | List categories | — | `{ categories[] }` |
| GET | `/api/v1/marketplace/:id` | Item detail | — | `{ ...item, versions[], reviews[] }` |
| POST | `/api/v1/marketplace/:id/install` | Install item | `{ version? }` | `{ installed: true, entryId }` |
| POST | `/api/v1/marketplace/:id/fork` | Fork item to workspace | — | `{ forkedId }` |
| POST | `/api/v1/marketplace/:id/reviews` | Submit review | `{ rating, review? }` | `{ id, ...review }` |

### 1.14 Runtime — Sandbox

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/sandbox/execute` | Execute code in Docker sandbox | `{ code, language, timeout?, dependencies? }` | `{ executionId, output, exitCode }` |
| POST | `/api/v1/sandbox/execute/stream` | Stream execution output (SSE) | Same as execute | SSE: `data: { type, content }` |
| GET | `/api/v1/sandbox/executions/:id` | Get execution result | — | `{ id, output, exitCode, duration }` |

### 1.15 Runtime — A2A Server

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/a2a/respond` | JSON-RPC 2.0: synchronous agent invocation | `{ jsonrpc: "2.0", method: "tasks/send", params: { message } }` | `{ jsonrpc: "2.0", result: { ... } }` |
| POST | `/a2a/message/send` | Send async message to agent | `{ taskId?, message }` | `{ taskId, status }` |
| GET | `/a2a/message/stream/:taskId` | Stream task updates (SSE) | — | SSE: `data: { status, artifacts[] }` |
| GET | `/api/v1/a2a/registry` | List A2A-capable agents | — | `{ agents: { name, skills[] }[] }` |

### 1.16 Runtime — MCP Server

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/mcp/tools/execute` | Execute MCP tool | `{ serverId, toolName, input }` | `{ output }` |
| GET | `/api/v1/mcp/tools` | List all MCP tools | Query: `?serverId=` | `{ tools[] }` |
| GET | `/api/v1/mcp/servers` | List MCP servers | — | `{ servers: { id, name, port, tools[] }[] }` |
| POST | `/api/v1/mcp/servers/:id/connect` | Connect to MCP server | — | `{ connected: true, tools[] }` |

### 1.17 Runtime — Deployer

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/api/v1/deployments` | Create deployment | `{ agentId, registryEntryId, target, config }` | `{ id, status: "PENDING" }` |
| GET | `/api/v1/deployments` | List deployments | Query: `?agentId=&status=&target=` | `{ items[] }` |
| POST | `/api/v1/deployments/:id/stop` | Stop deployment | — | `{ id, status: "STOPPED" }` |
| POST | `/api/v1/deployments/:id/rollback` | Rollback to previous version | `{ targetVersion? }` | `{ id, status: "DEPLOYING" }` |
| POST | `/api/v1/platform/deploy/:agent_name` | Deploy agent by name (platform shortcut) | `{ target?, config? }` | `{ deploymentId, status }` |
| POST | `/api/v1/platform/targets` | List available deployment targets | — | `{ targets[] }` |

### 1.18 Agent Runtime Endpoints

Each agent process (ports 9200-9250) exposes identical endpoints:

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/health` | Health check | — | `{ status: "healthy", agent, uptime }` |
| GET | `/ready` | Readiness probe | — | `{ status: "ready" }` |
| GET | `/info` | Agent metadata | — | `{ name, version, model, tools[], skills[] }` |
| POST | `/invocations` | Synchronous agent invocation | `{ message, conversationId?, userId? }` | `{ response, toolCalls[], usage }` |
| POST | `/invocations/stream` | Streaming invocation (SSE) | Same as invocations | SSE: `data: { type, content, toolCall?, done? }` |

---

## 2. Database Schema

PostgreSQL 16 with pgvector extension. 27 models across 7 domains. Managed via Prisma.

Schema file: `db/schemas/schema.prisma`

### 2.1 Entity Relationship Overview

```
User ──┬── RegistryEntry ──── RegistryVersion
       │        │──── RegistryDependency
       │        │──── RegistryRating ←── User
       │        └──── Deployment ──── DeploymentLog
       ├── TeamMember ──── Team ──── Budget ──── BudgetAlert
       ├── UserRole ──── Role
       ├── ApiKey
       ├── ApprovalRequest ──── ApprovalDecision ←── User
       ├── MemoryConfig
       ├── Conversation ──── Message
       └── VectorCollection

ModelConfig ──── RateLimit
GuardrailConfig (standalone)
Policy (standalone)
AuditLog (standalone)
CostRecord (standalone)
InferenceRecord (standalone)
```

### 2.2 Models Reference

#### Registry Domain

| Model | Key Fields | Description |
|-------|-----------|-------------|
| **RegistryEntry** | `id`, `resourceType`, `name`, `version`, `language`, `framework`, `configYaml`, `gitRepo`, `gitSha`, `authorId`, `isPublic`, `downloadCount` | Central registry for all platform artifacts (agents, tools, prompts, MCP servers, collections, models, memory configs) |
| **RegistryVersion** | `id`, `entryId`, `version`, `changelog`, `configYaml`, `gitSha` | Immutable version snapshots |
| **RegistryDependency** | `id`, `entryId`, `dependsOnId`, `versionConstraint` | Dependency graph between entries |
| **RegistryRating** | `id`, `entryId`, `userId`, `rating` (1-5), `review` | User ratings and reviews |

#### Auth Domain

| Model | Key Fields | Description |
|-------|-----------|-------------|
| **User** | `id`, `email`, `name`, `avatarUrl`, `provider`, `providerId` | Platform users (OAuth-linked) |
| **Team** | `id`, `name`, `description` | Organizational teams |
| **TeamMember** | `id`, `teamId`, `userId`, `role` (ADMIN/MEMBER/VIEWER) | Team membership with role |
| **Role** | `id`, `name`, `permissions` (JSON array), `isSystem` | RBAC role definitions |
| **UserRole** | `id`, `userId`, `roleId`, `scope` (GLOBAL/TEAM/PROJECT), `scopeId` | Role assignments with scoping |
| **ApiKey** | `id`, `userId`, `name`, `keyHash`, `scopes[]`, `expiresAt`, `lastUsedAt` | Hashed API keys with scoped permissions |

#### Governance Domain

| Model | Key Fields | Description |
|-------|-----------|-------------|
| **ApprovalRequest** | `id`, `resourceType`, `resourceId`, `action`, `requesterId`, `status`, `reason` | Approval workflow requests |
| **ApprovalDecision** | `id`, `requestId`, `approverId`, `decision`, `comment` | Individual approval/rejection decisions |
| **Policy** | `id`, `name`, `resourceType`, `conditions` (JSON), `actions` (JSON), `isActive` | Automated governance policies |
| **AuditLog** | `id`, `userId`, `action`, `resourceType`, `resourceId`, `details` (JSON), `ipAddress` | Immutable audit trail |

#### Model Gateway Domain

| Model | Key Fields | Description |
|-------|-----------|-------------|
| **ModelConfig** | `id`, `provider`, `modelId`, `modelType`, `displayName`, `endpoint`, `defaultParams` (JSON) | Registered model configurations |
| **RateLimit** | `id`, `modelId`, `scope`, `scopeId`, `requestsPerMinute`, `tokensPerMinute`, `burstLimit` | Per-model rate limits (user/team/global) |
| **GuardrailConfig** | `id`, `name`, `type`, `params` (JSON), `action`, `isActive` | Content safety guardrail definitions |

#### Cost Domain

| Model | Key Fields | Description |
|-------|-----------|-------------|
| **CostRecord** | `id`, `agentId`, `modelId`, `userId`, `teamId`, `tokensIn`, `tokensOut`, `costUsd`, `requestType` | Per-request cost events |
| **Budget** | `id`, `name`, `teamId`, `monthlyLimit`, `alertThresholds` (JSON array) | Team spending budgets |
| **BudgetAlert** | `id`, `budgetId`, `thresholdPercent`, `currentSpend`, `sentAt` | Triggered budget alerts |

#### Inference Domain

| Model | Key Fields | Description |
|-------|-----------|-------------|
| **InferenceRecord** | `id`, `agentId`, `modelId`, `userId`, `inputHash`, `inputPreview`, `outputPreview`, `tokensIn`, `tokensOut`, `latencyMs`, `costUsd`, `metadata` | Inference capture with previews (full payloads in S3) |

#### Deployment Domain

| Model | Key Fields | Description |
|-------|-----------|-------------|
| **Deployment** | `id`, `agentId`, `registryEntryId`, `target`, `status`, `config` (JSON), `endpoint`, `healthCheckUrl`, `deployedById` | Agent deployment records |
| **DeploymentLog** | `id`, `deploymentId`, `level`, `message` | Deployment event logs |

#### Memory Domain

| Model | Key Fields | Description |
|-------|-----------|-------------|
| **MemoryConfig** | `id`, `name`, `shortTermProvider`, `shortTermConfig`, `longTermProvider`, `longTermConfig`, `authorId` | Memory backend configurations |
| **Conversation** | `id`, `agentId`, `userId`, `metadata` | Conversation sessions |
| **Message** | `id`, `conversationId`, `role`, `content`, `toolCalls` (JSON), `metadata` | Individual messages |

#### Vector Domain

| Model | Key Fields | Description |
|-------|-----------|-------------|
| **VectorCollection** | `id`, `name`, `provider`, `embeddingModel`, `dimensions`, `metric`, `chunkingConfig`, `indexStatus`, `documentCount`, `authorId` | Vector search collection definitions |

### 2.3 Enums Reference

| Enum | Values |
|------|--------|
| `ResourceType` | AGENT, TOOL, PROMPT, MCP_SERVER, VECTOR_COLLECTION, MODEL, MEMORY_CONFIG |
| `Language` | PYTHON, TYPESCRIPT, KOTLIN |
| `Framework` | LANGCHAIN, LANGGRAPH, MASTRA, CREWAI, OPENAI_SDK, GOOGLE_ADK, CLAUDE_SDK, STRANDS_SDK, PYDANTIC_AI, AUTOGEN, KOOG, NONE |
| `AuthProvider` | DATABRICKS, GITHUB, GOOGLE |
| `TeamRole` | ADMIN, MEMBER, VIEWER |
| `RoleScope` | GLOBAL, TEAM, PROJECT |
| `ApprovalAction` | DEPLOY, UPDATE, DELETE, PUBLISH |
| `ApprovalStatus` | PENDING, APPROVED, REJECTED, CANCELED |
| `ApprovalDecisionType` | APPROVED, REJECTED |
| `ModelType` | TEXT, EMBEDDING, REASONING, IMAGE, VIDEO |
| `RateLimitScope` | USER, TEAM, GLOBAL |
| `GuardrailType` | PII_DETECTION, CONTENT_FILTER, TOXICITY, HALLUCINATION, CUSTOM |
| `GuardrailAction` | BLOCK, REDACT, WARN, LOG |
| `DeploymentTarget` | EKS, DATABRICKS_APP, GKE |
| `DeploymentStatus` | PENDING, BUILDING, DEPLOYING, RUNNING, FAILED, STOPPED |
| `LogLevel` | INFO, WARN, ERROR |
| `MessageRole` | SYSTEM, USER, ASSISTANT, TOOL |
| `VectorProvider` | DATABRICKS, ELASTIC, PGVECTOR, PINECONE, WEAVIATE, QDRANT |
| `IndexStatus` | CREATING, READY, FAILED |

---

## 3. Agent Configuration Format

Agents are defined as `agent.yaml` + `prompt.md` files in the `agents/` directory. The runtime reads, merges, and validates these files at startup.

### 3.1 Config Merge Hierarchy

Configuration is resolved in order (later layers override earlier):

| Priority | Source | Path | Purpose |
|----------|--------|------|---------|
| 1 (lowest) | Global defaults | `agents/@global/agent.yaml` | Model, memory, streaming defaults |
| 2 | Agent config | `agents/{name}/agent.yaml` | Agent-specific configuration |
| 3 | Environment overlay | `agents/{name}/agent.{NODE_ENV}.yaml` | Per-environment overrides (production, staging) |
| 4 | Local overrides | `agents/{name}/agent.local.yaml` | Developer-local (gitignored) |
| 5 (highest) | Environment variables | `AGENT_*` prefixed vars | Runtime overrides |

### 3.2 Complete YAML Schema Reference

```yaml
agent:
  # ── Identity ──────────────────────────────────────────────────────
  name: my-agent                          # Required. Unique identifier (kebab-case)
  display_name: "My Agent"                # Optional. Human-friendly name
  version: "1.0.0"                        # Required. Semver
  description: "Agent description"        # Required. Purpose description
  tags: ["support", "internal"]           # Optional. Categorization tags

  # ── Framework ─────────────────────────────────────────────────────
  framework: mastra                       # Optional. mastra | langchain | langgraph |
                                          # crewai | openai_agents | google_adk |
                                          # strands | pydantic_ai | autogen | koog | custom

  # ── Model ─────────────────────────────────────────────────────────
  model:
    provider: anthropic                   # Required. See Section 4 for all providers
    name: claude-sonnet-4-5               # Required. Model identifier
    temperature: 0.7                      # Optional. 0-2
    max_tokens: 4096                      # Optional. Max output tokens
    top_p: 0.9                            # Optional. Nucleus sampling (0-1)
    top_k: 40                             # Optional. Top-k sampling (Anthropic/Google)
    stop_sequences: ["END"]               # Optional. Stop generation tokens
    frequency_penalty: 0.0                # Optional. -2 to 2 (OpenAI/Databricks)
    presence_penalty: 0.0                 # Optional. -2 to 2 (OpenAI/Databricks)
    seed: null                            # Optional. Deterministic sampling (OpenAI)
    timeout: 30000                        # Optional. HTTP request timeout (ms)
    max_retries: 2                        # Optional. Auto-retry on transient errors
    base_url: "https://..."               # Optional. Custom endpoint URL
    gateway_url: "http://..."             # Optional. Model Gateway proxy URL
    reasoning_effort: "medium"            # Optional. Reasoning effort level

    thinking:                             # Optional. Extended thinking (Claude)
      type: adaptive                      # enabled | disabled | adaptive
      budget_tokens: 8192                 # Token budget for thinking

    safety_settings:                      # Optional. Google AI only
      - category: HARM_CATEGORY_HATE_SPEECH
        threshold: BLOCK_MEDIUM_AND_ABOVE

    cache_control:                        # Optional. Prompt caching (Anthropic)
      type: ephemeral
      ttl: 300

    retry:                                # Optional. Retry policy
      max_attempts: 3
      backoff_factor: 2.0
      jitter: true

    fallback_model:                       # Optional. Fallback on primary failure
      provider: openai
      name: gpt-4o
      base_url: "https://..."

  # ── Prompts ───────────────────────────────────────────────────────
  system_prompt_ref: prompt.md            # Optional. Path to prompt file (relative to agent dir)
  system_prompt: "You are a helpful..."   # Optional. Inline prompt (system_prompt_ref preferred)

  # ── Tools ─────────────────────────────────────────────────────────
  tools:                                  # Optional. Toolkit dotted paths
    - uap_toolkit.zendesk.search_help_articles
    - uap_toolkit.databricks.query.submit_query
    - uap_toolkit.cip.content_quality.assess_professionalism

  tool_choice: auto                       # Optional. auto | required | none | {tool_name}
  parallel_tool_calls: true               # Optional. Allow parallel tool execution
  max_iterations: 10                      # Optional. Max tool-call cycles
  max_execution_time: 300                 # Optional. Total timeout (seconds)

  hosted_tools:                           # Optional. Provider-hosted tools
    - type: web_search                    # web_search | code_interpreter | computer_use |
      provider: brave                     # file_search | image_generation
      config: {}

  # ── Subagents ─────────────────────────────────────────────────────
  subagents:                              # Optional. Agent-to-agent delegation
    - agent_name: helper-agent            # Target agent name
      tool_name: ask_helper               # Tool name exposed to LLM
      description: "Delegate to helper"   # Tool description
      timeout_seconds: 60                 # Optional. Call timeout

  # ── MCP Connections ───────────────────────────────────────────────
  mcps:                                   # Optional. MCP server connections
    zendesk:
      transport: http
      url: http://localhost:9100
    local-tool:
      transport: stdio
      command: npx
      args: ["-y", "@my/mcp-server"]

  # ── Memory ────────────────────────────────────────────────────────
  memory:
    type: buffer_window                   # buffer_window | buffer | summary | entity | vector_store
    backend: in_memory                    # in_memory | redis | postgresql
    max_messages: 20
    connection_url: "redis://..."         # Optional. Override env var
    user_isolation: true                  # Optional. Namespace by user ID
    semantic_recall:                      # Optional. Semantic memory search
      enabled: true
      top_k: 5
      score_threshold: 0.7
      embeddings:                         # Optional. Embedding config for recall
        provider: openai
        model: text-embedding-3-small
        dimensions: 1536

  # ── Vector Search / RAG ───────────────────────────────────────────
  vector_search_indexes:                  # Optional. Auto-generates search_* tools
    - index_name: prod.schema.my_index    # Fully qualified index name
      provider: databricks                # databricks | elasticsearch
      num_results: 5
      query_type: HYBRID                  # ANN | HYBRID
      columns: ["id", "content"]
      filters: {}
      score_threshold: 0.7
      description: "Search knowledge base"
      # Databricks-specific
      source_table: prod.schema.source
      endpoint_name: vs-endpoint
      primary_key: id
      embedding_source_column: content
      embedding_model: databricks-gte-large-en
      pipeline_type: TRIGGERED            # TRIGGERED | CONTINUOUS
      # Elasticsearch-specific
      es_index_name: my-es-index
      es_embedding_field: embedding
      es_content_field: content
      dimensions: 1536
      metric: cosine                      # cosine | l2 | inner_product

  # ── Structured Output ─────────────────────────────────────────────
  output_schema:                          # Optional. JSON Schema for structured output
    type: object
    properties:
      answer: { type: string }
    required: [answer]

  output:                                 # Optional. Output formatting
    schema: {}                            # JSON Schema
    citations: { enabled: true }
    format: json                          # text | json | markdown

  # ── Guardrails ────────────────────────────────────────────────────
  guardrails:
    input:
      - type: content_policy              # content_policy | pii_redaction | token_limit | custom
        action: block                     # block | warn | log
        config: {}
    output:
      - type: pii_redaction
        action: warn
    max_retries: 2                        # Retry on guardrail failure

  # ── Human-in-the-Loop ────────────────────────────────────────────
  human_in_the_loop:
    interrupt_before: [dangerous_tool]    # Pause before these tools
    interrupt_after: [review_tool]        # Pause after these tools
    approval_timeout: 300                 # Seconds before auto-reject

  # ── Observability ─────────────────────────────────────────────────
  tracing:
    enabled: true
    provider: otel                        # otel | langsmith | custom
    metadata:
      team: platform

  # ── Lifecycle Hooks ───────────────────────────────────────────────
  hooks:
    before_model: uap_toolkit.hooks.log_request
    after_model: uap_toolkit.hooks.log_response
    before_tool: null
    after_tool: null

  # ── Streaming ─────────────────────────────────────────────────────
  streaming:
    enabled: true
    protocol: sse

  # ── A2A Protocol ──────────────────────────────────────────────────
  protocol: a2a
  a2a:
    skills:
      - name: classify_topic
        description: "Classify content topics"
        input_modes: ["text/plain"]
        output_modes: ["application/json"]

  # ── Code Execution ────────────────────────────────────────────────
  code_execution:
    enabled: true
    mode: sandbox                         # sandbox | local
    timeout: 30

  # ── Planner ───────────────────────────────────────────────────────
  planner:
    type: react                           # none | react | plan_and_execute
    thinking_budget: 8192

  # ── Orchestration ─────────────────────────────────────────────────
  orchestration:
    process: sequential                   # sequential | hierarchical | consensus
    delegation:
      allow_delegation: true
      max_depth: 3

  # ── Workflow (LangGraph / Mastra) ─────────────────────────────────
  workflow:
    type: dag                             # dag | graph | sequential | parallel | loop
    entry_point: classifier
    finish_point: responder
    nodes:
      - name: classifier
        type: conditional
        condition: "classify_input"
        routes:
          support: support_handler
          sales: sales_handler
      - name: support_handler
        type: agent
        agent_ref: support-agent
        tools: [uap_toolkit.zendesk.search_help_articles]
    edges:
      - { from: classifier, to: support_handler, condition: "support" }
    checkpointer:
      enabled: true
      backend: postgresql
      connection_string_env: DATABASE_URL

  # ── Handoffs (OpenAI Agents SDK) ─────────────────────────────────
  handoffs:
    - target_agent: specialist-agent
      tool_name: escalate_to_specialist
      tool_description: "Escalate complex issues"
      input_filter: summary_only          # full | summary_only | last_message

  # ── CrewAI Persona ────────────────────────────────────────────────
  persona:
    role: "Senior Research Analyst"
    goal: "Provide comprehensive analysis"
    backstory: "Expert analyst with 10+ years..."
    allow_delegation: true
    max_iter: 15

  # ── CrewAI Tasks ──────────────────────────────────────────────────
  tasks:
    - name: research
      description: "Research the topic"
      expected_output: "Detailed report"
      agent_ref: researcher
      async_execution: false

  # ── Session (Google ADK / Strands) ────────────────────────────────
  session:
    service: database                     # in_memory | database | dynamodb | vertex_ai | file | redis
    config: {}
    state_template: { user_name: "" }
    artifacts:
      enabled: true
      storage: s3

  # ── Evaluation ────────────────────────────────────────────────────
  evaluation:
    enabled: true
    judge_model: openai:/gpt-4o-mini
    metrics: [completeness, relevance, faithfulness]
    test_cases_file: tests/eval.json
    thresholds:
      completeness: 0.8
      relevance: 0.8

  # ── Voice Pipeline ────────────────────────────────────────────────
  voice:
    enabled: true
    stt: { provider: openai, model: whisper-1 }
    tts: { provider: elevenlabs, voice: adam }

  # ── Agent Network (Mastra) ───────────────────────────────────────
  agent_network:
    name: support-network
    agents: [support-agent, billing-agent, tech-agent]
    default_agent: support-agent
    routing_strategy: llm_based           # llm_based | round_robin | skill_match | cost_optimized

  # ── Deployment ────────────────────────────────────────────────────
  deployment:
    target: eks                           # See Section 8 for all targets
    runtime: typescript                   # typescript | python | kotlin
    port: 9200
    region: us-east-1
    registry: 123456789.dkr.ecr.us-east-1.amazonaws.com
    deployer_class: my_package.MyDeployer # Optional. Custom deployer
    deployer_config: {}
    resources:
      cpu: "500m"
      memory: "1Gi"
      gpu: "0"
      min_instances: 1
      max_instances: 10
    scaling:
      metric: cpu                         # cpu | memory | requests | queue_depth | custom
      target: 70
      cooldown: 60
    health_check:
      path: /health
      interval: 30
      timeout: 5
      healthy_threshold: 2
      unhealthy_threshold: 3
    env:
      - name: API_KEY
        value: ""
        secret: true

  # ── Misc ──────────────────────────────────────────────────────────
  environment_variables:
    CUSTOM_VAR: "value"
  dependencies: ["langchain>=0.3"]
  requires_python: ">=3.11,<3.13"
  model_extra: {}                         # Databricks model_extra passthrough
  unity_catalog_functions: []             # Databricks UC function references
  artifact_tracking:
    provider: mlflow                      # mlflow | wandb | neptune | custom
    experiment_name: my-experiment
  offline_evaluation:
    enabled: true
    judge_model: openai:/gpt-4o-mini
    thresholds:
      correctness: 0.7
      safety: 0.95
```

---

## 4. Model Provider Reference

The `model.provider` field accepts any string. Well-known providers have native SDK support; unknown providers are treated as OpenAI-compatible endpoints.

### 4.1 Well-Known Providers

| Provider | SDK | Models (examples) | Notes |
|----------|-----|-------------------|-------|
| `anthropic` | Anthropic SDK | claude-sonnet-4-5, claude-haiku-3.5 | Native thinking support, cache_control |
| `openai` | OpenAI SDK | gpt-4o, gpt-4.1, o3-mini | seed, structured outputs, function calling |
| `google` | Google AI SDK | gemini-2.5-pro, gemini-2.0-flash | safety_settings, code_execution |
| `bedrock` | AWS Bedrock SDK | anthropic.claude-v3, amazon.titan | AWS credentials required |
| `azure` | Azure OpenAI SDK | gpt-4o (deployment name) | Requires base_url with deployment |
| `databricks` | OpenAI-compatible | databricks-claude-sonnet-4-5, databricks-dbrx | Uses `{DATABRICKS_HOST}/serving-endpoints` |
| `gateway` | HTTP client | Any registered model | Routes through Model Gateway (:8080) |
| `litellm` | HTTP client | Any litellm model string | LiteLLM proxy |
| `openrouter` | OpenAI-compatible | anthropic/claude-3-opus, etc. | `base_url: https://openrouter.ai/api/v1` |
| `together` | OpenAI-compatible | meta-llama/Llama-3-70b-chat | `base_url: https://api.together.xyz/v1` |
| `fireworks` | OpenAI-compatible | accounts/fireworks/models/... | `base_url: https://api.fireworks.ai/inference/v1` |
| `perplexity` | OpenAI-compatible | sonar-medium-online | `base_url: https://api.perplexity.ai` |
| `xai` | OpenAI-compatible | grok-2 | `base_url: https://api.x.ai/v1` |
| `deepseek` | OpenAI-compatible | deepseek-chat, deepseek-coder | `base_url: https://api.deepseek.com/v1` |
| `moonshot` | OpenAI-compatible | moonshot-v1-8k | `base_url: https://api.moonshot.cn/v1` |
| `groq` | OpenAI-compatible | llama3-70b-8192, mixtral-8x7b | `base_url: https://api.groq.com/openai/v1` |
| `mistral` | OpenAI-compatible | mistral-large-latest | `base_url: https://api.mistral.ai/v1` |
| `cohere` | OpenAI-compatible | command-r-plus | `base_url: https://api.cohere.ai/v1` |

### 4.2 OpenAI-Compatible Fallback

Any provider string not in the well-known list is treated as OpenAI-compatible. You must supply `base_url`:

```yaml
model:
  provider: my-company-llm
  name: internal-model-v2
  base_url: https://llm.internal.company.com/v1
```

The runtime uses the OpenAI SDK with the custom `base_url` and looks for the API key in the `{PROVIDER_UPPER}_API_KEY` environment variable (e.g., `MY_COMPANY_LLM_API_KEY`).

---

## 5. Tool System

### 5.1 Toolkit Registry (22 modules, 83+ tools)

Tools are referenced in agent YAML via dotted paths: `uap_toolkit.{namespace}.{tool_name}`.

| Namespace | Path Prefix | Tools | Description |
|-----------|-------------|-------|-------------|
| `zendesk` | `uap_toolkit.zendesk.*` | 1 | `search_help_articles` — Search Zendesk via MCP |
| `course_catalog` | `uap_toolkit.course_catalog.*` | 2 | Course search and details via MCP |
| `featurestore` | `uap_toolkit.featurestore.*` | 2 | Feature store queries via MCP |
| `learner_state` | `uap_toolkit.learner_state.*` | 2 | Learner progress tracking via MCP |
| `learner_state_agent` | `uap_toolkit.learner_state_agent.*` | 1 | Learner state agent delegation via MCP |
| `learner_profile` | `uap_toolkit.learner_profile.*` | 2 | Learner profile queries via MCP |
| `goal_elicitation` | `uap_toolkit.goal_elicitation.*` | 2 | Learning goal extraction via MCP |
| `tutor` | `uap_toolkit.tutor.*` | 1 | Tutoring interaction via MCP |
| `s3_persist` | `uap_toolkit.s3_persist.*` | 2 | S3 read/write persistence via MCP |
| `execute_query` | `uap_toolkit.execute_query.*` | 1 | SQL execution via MCP |
| `onboarding` | `uap_toolkit.onboarding.*` | 1 | User onboarding via MCP |
| `lecture_lo` | `uap_toolkit.lecture_lo.*` | 2 | Lecture learning objectives via MCP |
| `inline` | `uap_toolkit.inline.*` | 2 | `calculate`, `echo` — No MCP, runs in-process |
| `memory` | `uap_toolkit.memory.*` | 3 | `store_memory`, `retrieve_memory`, `search_memory` |
| `databricks.query` | `uap_toolkit.databricks.query.*` | 2 | `submit_query`, `retrieve_query_result` |
| `databricks.user` | `uap_toolkit.databricks.user.*` | 1 | `get_current_user` |
| `databricks.lineage` | `uap_toolkit.databricks.lineage.*` | 2 | `get_table_lineage`, `get_column_lineage` |
| `databricks.job` | `uap_toolkit.databricks.job.*` | 4 | `list_databricks_jobs`, `get_databricks_job`, `list_recent_databricks_job_runs`, `get_databricks_job_run` |
| `atlassian` | `uap_toolkit.atlassian.*` | 4 | Jira issues + Confluence wiki search |
| `airflow.dag` | `uap_toolkit.airflow.dag.*` | 9 | `list_dags`, `get_dag`, `get_dag_run`, `get_recent_dag_runs`, `get_task_instance`, `parse_airflow_url`, `trigger_dag_run`, `update_task_instance_state`, `clear_task_instance` |
| `common` | `uap_toolkit.common.*` | 2 | `sleep`, `echo` |
| `taxonomy` | `uap_toolkit.taxonomy.*` | 1 | `save_topic_recommendation` |
| `cip.content_quality` | `uap_toolkit.cip.content_quality.*` | 10 | 8-dimension quality scoring, professionalism assessment |

### 5.2 MCP Servers (13 servers)

| Port | Server | Tools Provided |
|------|--------|---------------|
| 9100 | Zendesk MCP | Help article search |
| 9101 | Course Catalog MCP | Course search, course details |
| 9102 | Feature Store MCP | Feature queries |
| 9103 | Learner State MCP | Progress tracking |
| 9104 | Learner State Agent MCP | Agent delegation |
| 9105 | Learner Profile MCP | Profile queries |
| 9106 | Goal Elicitation MCP | Goal extraction |
| 9107 | Tutor MCP | Tutoring |
| 9108 | S3 Persist MCP | Object storage |
| 9109 | Execute Query MCP | SQL execution |
| 9110 | Onboarding MCP | Onboarding flows |
| 9111 | Lecture LO MCP | Learning objectives |
| 9112 | Course Catalog Extended MCP | Extended course data |

### 5.3 Vector Search Auto-Tools

When `vector_search_indexes` is declared in agent YAML, the runtime automatically generates `search_{index_name_suffix}` tools. For example:

```yaml
vector_search_indexes:
  - index_name: prod.content_intelligence.approved_topics_idx
    num_results: 5
    query_type: HYBRID
```

Generates a tool named `search_approved_topics_idx` that accepts a `query` string parameter and returns matching documents.

**Databricks provider:** Calls REST API `POST /api/2.0/vector-search/indexes/{index_name}/query` with `query_text` (auto-embedded server-side).

**Elasticsearch provider:** Uses kNN search or hybrid (kNN + BM25 with 0.7/0.3 boost weighting). Score threshold filtering applied post-query.

---

## 6. UI Pages Reference

React SPA at port 3000. Built with Vite + React 19 + TanStack Router.

### 6.1 Pages

| Route | Page | Key Components | API Endpoints Used |
|-------|------|---------------|-------------------|
| `/` | Control Center | AgentCards, PipelineCards, QuickStats, ChatTabs | `/agents`, `/deployments`, `/costs/summary`, `/health` |
| `/chat` | Chat | ChatPanel, MessageList, ToolCallRenderer, StreamViewer | Agent `/invocations/stream`, `/conversations` |
| `/agent-builder` | Agent Builder | VisualCanvas (ReactFlow), YAMLEditor (Monaco), PromptEditor, IDEPanel | `/agents`, `/agents/:id/generate`, `/agents/filesystem/:name`, `/templates`, `/toolkit/tools` |
| `/prompt-builder` | Prompt Builder | PromptList, PromptEditor, VariablePanel, TestRunner | `/prompts`, `/prompts/:id/test`, `/prompts/:id/versions` |
| `/tool-builder` | Tool Builder | ToolList, CodeEditor, SchemaEditor, ExecutionPanel | `/tools`, `/tools/:id/execute`, `/tools/:id/validate` |
| `/rag-builder` | RAG Builder | CollectionList, IngestPanel, QueryTester, ChunkingConfig | `/vector-collections`, `/vector-collections/:id/ingest`, `/vector-collections/:id/query` |
| `/memory-builder` | Memory Builder | ConfigList, ConversationViewer, MessageTimeline | `/memory-configs`, `/conversations`, `/memory/recall` |
| `/marketplace` | Marketplace | BrowseGrid, FeaturedBanner, ReviewPanel, InstallButton | `/marketplace`, `/marketplace/featured`, `/marketplace/:id/install` |
| `/registry` | Registry | EntryTable, VersionHistory, DependencyGraph, GitSyncStatus | `/registry`, `/git/status` |
| `/monitoring` | Monitoring | HealthMatrix, MetricsCharts, TraceViewer, AlertRules | `/health`, `/metrics`, `/traces`, `/alerts` |
| `/cost-dashboard` | Cost Dashboard | SpendChart, BudgetCards, BreakdownTable, ForecastPanel | `/costs/summary`, `/costs/breakdown`, `/budgets` |
| `/governance` | Governance | ApprovalQueue, PolicyEditor, AuditTimeline | `/approvals`, `/policies`, `/audit` |
| `/deployments` | Deployments | DeploymentList, LogViewer, TargetSelector, RollbackButton | `/deployments`, `/platform/targets` |
| `/model-registry` | Model Registry | ModelTable, RateLimitEditor, GuardrailManager | `/models`, `/models/catalog`, `/rate-limits`, `/guardrails` |
| `/settings` | Settings | ProfileEditor, TeamManager, ApiKeyManager, ThemeSelector | `/users`, `/teams`, `/api-keys` |

### 6.2 Agent Builder Modes

The agent builder supports 4 editing modes mapping to the 3-tier authoring model:

| Mode | Tier | Editor | Description |
|------|------|--------|-------------|
| **Visual** | No-Code | ReactFlow canvas with 10 node types (Agent, Model, Prompt, Tool, Subagent, Memory, RAG, MCP, A2A, Guardrail) | Drag-and-drop graph editing; auto-generates YAML |
| **YAML** | Low-Code | Monaco editor with DIP schema completions, validation markers, insert snippets | Direct YAML editing with autocomplete |
| **Prompt** | Low-Code | Markdown editor with live preview | Edit `prompt.md` content |
| **IDE** | Full Code | Multi-file editor with 16 generators (8 Python + 6 TypeScript + 1 Kotlin), framework selector, sandbox execution, AI assistant | Full code generation + editing; ZIP export |

---

## 7. Authentication & Authorization

### 7.1 OAuth2 Flow

1. Client redirects to `GET /api/v1/auth/login/:provider` (databricks, github, or google)
2. Server redirects to provider's authorization URL with `state` + PKCE `code_verifier`
3. Provider redirects back to `GET /api/v1/auth/callback/:provider?code=...&state=...`
4. Server exchanges code for tokens, creates/updates User record, issues JWT pair

### 7.2 JWT Structure

**Access Token** (short-lived, 15 minutes):
```json
{
  "sub": "uuid",
  "email": "user@udemy.com",
  "name": "User Name",
  "roles": ["admin", "deployer"],
  "teams": ["platform-team"],
  "iat": 1709000000,
  "exp": 1709000900,
  "iss": "unified-agent-platform"
}
```

**Refresh Token** (long-lived, 7 days): Opaque token stored hashed in the database.

### 7.3 Authentication Middleware

The `authMiddleware` in `src/middleware/auth.ts` runs on all routes except:

- `GET /health`, `GET /ready` -- health checks
- `GET /metrics` -- Prometheus scraping
- `GET /.well-known/agent.json` -- A2A discovery

It validates the `Authorization: Bearer <token>` header and injects `req.user` with decoded claims.

### 7.4 RBAC Model

Roles are defined in the `Role` table with JSON `permissions` arrays:

```json
[
  { "resource": "agents", "action": "create" },
  { "resource": "agents", "action": "deploy" },
  { "resource": "deployments", "action": "*" }
]
```

**Scoping:** Each `UserRole` assignment has a `scope` (GLOBAL, TEAM, PROJECT) and optional `scopeId` to restrict permissions to a team or project context.

**System Roles** (seeded, `isSystem: true`):

| Role | Permissions |
|------|------------|
| `admin` | `*` on all resources |
| `developer` | CRUD on agents, tools, prompts, collections; deploy to non-prod |
| `operator` | Read all; deploy/stop/rollback; manage budgets |
| `viewer` | Read-only on all resources |

### 7.5 API Key Authentication

API keys are an alternative to OAuth2 for programmatic access:

- Created via `POST /api/v1/api-keys` with scoped permissions
- Sent as `Authorization: Bearer uap_...` or `X-API-Key: uap_...`
- Stored as SHA-256 hash; original key returned only at creation time
- Optional expiration; `lastUsedAt` updated on each use

### 7.6 Rate Limiting

Three tiers applied via `src/middleware/rate-limit.ts`:

| Tier | Prefix | Window | Limit | Purpose |
|------|--------|--------|-------|---------|
| Auth | `/api/v1/auth` | 15 min | 20 requests | Prevent brute-force |
| Inference | `/api/v1/inference` | 1 min | 60 requests | Protect LLM endpoints |
| Default | `/api/v1/*` | 1 min | 200 requests | General API protection |

Rate limits are per-user (keyed by JWT `sub` or API key ID). Redis-backed when available; falls back to in-memory.

---

## 8. Deployment Targets

The deployer module supports 10 deployment targets. Each target implements the same interface: build image, push to registry, create/update service, configure networking, run health checks.

### 8.1 Target Reference

| Target | Config Key | Infrastructure | Scaling | Health Check |
|--------|-----------|---------------|---------|-------------|
| **Docker** | `docker` | Local Docker daemon | Manual | HTTP GET /health |
| **Kubernetes** | `k8s` | Generic K8s cluster | HPA (cpu/memory/custom) | Liveness + readiness probes |
| **Amazon EKS** | `eks` | AWS EKS cluster | HPA + Karpenter | ALB health checks |
| **Google GKE** | `gke` | Google GKE cluster | HPA + node auto-provisioning | GCE health checks |
| **Amazon ECS** | `ecs` | AWS ECS on EC2 | Service auto-scaling | ELB health checks |
| **AWS Fargate** | `fargate` | AWS ECS Fargate (serverless) | Task auto-scaling | ALB health checks |
| **Google Cloud Run** | `cloud_run` | GCP Cloud Run (serverless) | Concurrency-based | Built-in |
| **Azure Container Apps** | `container_apps` | Azure Container Apps | KEDA-based | Built-in |
| **Oracle OKE** | `oke` | Oracle Container Engine | HPA | OCI health checks |
| **AWS Bedrock** | `bedrock` | AWS Bedrock custom model hosting | Provisioned throughput | Built-in |
| **Databricks** | `databricks` | Databricks Apps (serverless) | Auto-managed | Built-in |

### 8.2 Deployment Configuration Example

```yaml
deployment:
  target: eks
  runtime: typescript
  port: 9200
  region: us-east-1
  registry: 123456789.dkr.ecr.us-east-1.amazonaws.com/uap

  resources:
    cpu: "500m"
    memory: "1Gi"
    gpu: "0"
    min_instances: 2
    max_instances: 20

  scaling:
    metric: requests          # Scale based on request rate
    target: 100               # Target requests per second per pod
    cooldown: 120             # Seconds before scaling down

  health_check:
    path: /health
    interval: 30
    timeout: 5
    healthy_threshold: 2
    unhealthy_threshold: 3

  env:
    - name: ANTHROPIC_API_KEY
      secret: true            # Fetched from secrets manager
    - name: LOG_LEVEL
      value: "info"
```

### 8.3 Deployment Lifecycle

```
POST /api/v1/deployments
  │
  ├─ Status: PENDING ─── Validate config, resolve registry entry
  │
  ├─ Status: BUILDING ── docker build, docker push to registry
  │
  ├─ Status: DEPLOYING ─ Create/update target resources (K8s Deployment, Cloud Run Service, etc.)
  │
  ├─ Status: RUNNING ─── Health checks passing, endpoint live
  │
  └─ Status: FAILED ──── Build or deploy error (check DeploymentLog)
```

Rollback creates a new deployment pointing to the previous registry version. Stop drains active connections before terminating.

### 8.4 Infrastructure as Code

Production deployments are managed via Terraform modules in `deploy/terraform/`:

| Module | Purpose | Resources |
|--------|---------|-----------|
| `dev/` | Development environment | EKS cluster, RDS, Redis, S3 |
| `eks/` | EKS cluster configuration | Node groups, IRSA, ALB controller |
| `gke/` | GKE cluster configuration | Node pools, Workload Identity |
| `rds/` | PostgreSQL database | RDS instance, parameter groups, security groups |
| `s3/` | Object storage | S3 buckets for inference capture, artifacts |

Helm chart at `deploy/helm/unified-agent-platform/` packages the unified app + agent runtimes for Kubernetes deployment. ArgoCD manifests in `deploy/argocd/` handle GitOps for 3 regions.

---

## Appendix: Request/Response Conventions

All API responses follow consistent patterns:

**Success (single item):**
```json
{ "id": "uuid", "name": "...", "createdAt": "2026-03-10T..." }
```

**Success (list):**
```json
{ "items": [...], "total": 42, "page": 1, "limit": 20 }
```

**Error:**
```json
{ "error": "Human-readable message", "code": "VALIDATION_ERROR", "details": [...] }
```

**HTTP Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Validation error (Zod schema failure) |
| 401 | Missing or invalid authentication |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 409 | Conflict (duplicate name/version) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

All request bodies are validated with Zod schemas via the `validate()` middleware before reaching route handlers.
