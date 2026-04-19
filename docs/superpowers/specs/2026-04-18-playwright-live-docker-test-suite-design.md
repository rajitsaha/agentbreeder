# Playwright Live Docker Test Suite — Design Spec

**Date:** 2026-04-18  
**Author:** Rajit Saha  
**Status:** Approved  

---

## Overview

An exhaustive Playwright end-to-end test suite that runs against the live AgentBreeder Docker stack (Postgres + Redis + FastAPI + LiteLLM + React dashboard). Covers all UI-accessible features: provider registration, prompts, tools, RAG, MCP servers, agent creation (no-code + low-code), agent execution, tracing, evals, cost monitoring, and RBAC.

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend | Live Docker | Tests real data persistence, registry writes, sandbox execution |
| Isolation | Hybrid — independent domains, ordered steps within each | Domain failures don't cascade; within-domain steps share setup |
| LLM calls | Registry-only for cloud providers; real for Ollama; LiteLLM fake for sandbox | No API keys required for CI; Ollama is local and free |
| RBAC users | Programmatically created in global setup | Self-contained, no pre-seeded state required |

---

## Directory Structure

```
dashboard/
├── tests/
│   └── e2e-live/
│       ├── global.setup.ts           # Create users, teams, seed LiteLLM fake model
│       ├── global.teardown.ts        # Delete all e2e-* resources + test users
│       ├── fixtures.ts               # adminPage, memberPage, viewerPage, api(), helpers
│       ├── helpers.ts                # waitForToast, fillYamlEditor, openSandbox
│       ├── 01-providers.spec.ts
│       ├── 02-prompts.spec.ts
│       ├── 03-tools.spec.ts
│       ├── 04-rag.spec.ts
│       ├── 05-mcp-servers.spec.ts
│       ├── 06-agents-nocode.spec.ts
│       ├── 07-agents-lowcode.spec.ts
│       ├── 08-agent-execution.spec.ts
│       ├── 09-tracing.spec.ts
│       ├── 10-evals.spec.ts
│       ├── 11-costs.spec.ts
│       └── 12-rbac.spec.ts
├── playwright.config.live.ts         # Separate config targeting live Docker
└── .auth/                            # Saved auth state (gitignored)
    ├── admin.json
    ├── member.json
    └── viewer.json
```

---

## Playwright Config (`playwright.config.live.ts`)

```typescript
// Target: http://localhost:3001 (dashboard) + http://localhost:8000 (API)
// Browsers: Chromium only
// Timeout: 60s per test (live Docker is slower than mocked)
// Retries: 1 (transient Docker startup issues)
// Screenshots + video: on failure only
// Workers: 3 (one per role context)
// Projects:
//   setup   → global.setup.ts    (runs first, no parallelism)
//   live    → *.spec.ts          (depends on setup)
//   teardown → global.teardown.ts (runs last, always)
```

**npm scripts (add to `dashboard/package.json`):**
```json
"test:e2e:live":    "playwright test --config=playwright.config.live.ts",
"test:e2e:live:ui": "playwright test --config=playwright.config.live.ts --ui",
```

---

## Global Setup (`global.setup.ts`)

Runs once before all specs via Playwright `setup` project dependency.

### Steps (in order):

1. **Register test users** via `POST /api/v1/auth/register`:
   - `e2e-admin@test.local` / `E2eAdmin123!` → role: admin
   - `e2e-member@test.local` / `E2eMember123!` → role: member
   - `e2e-viewer@test.local` / `E2eViewer123!` → role: viewer

2. **Save auth state** via `page.context().storageState()` → `.auth/admin.json`, `.auth/member.json`, `.auth/viewer.json`

3. **Create teams** (as admin):
   - `e2e-team-alpha` — member + viewer are members
   - `e2e-team-beta` — admin only (used for cross-team RBAC isolation tests)

4. **Register LiteLLM fake provider** via `POST /api/v1/providers`:
   ```json
   { "name": "e2e-litellm-fake", "type": "litellm", "base_url": "http://localhost:4000", "model": "fake/gpt-4" }
   ```

5. **Write shared state** to `.e2e-state.json`:
   ```json
   { "adminId": "...", "memberId": "...", "viewerId": "...", "teamAlphaId": "...", "teamBetaId": "...", "providerId": "..." }
   ```

---

## Global Teardown (`global.teardown.ts`)

Runs once after all specs (even if specs fail).

1. As admin: `DELETE /api/v1/agents?name_prefix=e2e-`
2. As admin: `DELETE /api/v1/prompts?name_prefix=e2e-`
3. As admin: `DELETE /api/v1/tools?name_prefix=e2e-`
4. As admin: `DELETE /api/v1/rag?name_prefix=e2e-`
5. As admin: `DELETE /api/v1/mcp_servers?name_prefix=e2e-`
6. As admin: `DELETE /api/v1/providers?name_prefix=e2e-`
7. As admin: `DELETE /api/v1/evals/datasets?name_prefix=e2e-`
8. As admin: `DELETE /api/v1/teams/e2e-team-alpha` and `e2e-team-beta`
9. As admin: delete 3 test user accounts

---

## Fixtures (`fixtures.ts`)

```typescript
// Extends Playwright base test with:

adminPage   // browser context loaded from .auth/admin.json
memberPage  // browser context loaded from .auth/member.json
viewerPage  // browser context loaded from .auth/viewer.json

api(role: 'admin'|'member'|'viewer')
// Returns fetch wrapper authenticated with that role's JWT
// Usage: await api('admin').post('/api/v1/prompts', body)

waitForToast(page, text)
// Asserts a toast notification containing `text` appears within 5s

fillYamlEditor(page, yaml)
// Clicks the CodeMirror editor, selects all, types the yaml string

openSandbox(page, agentName)
// Navigates to /playground, selects the agent by name, returns page
```

---

## Spec Files

### `01-providers.spec.ts`

**Scope:** Register all supported LLM providers; verify they appear in model catalog; deregister one.

| # | Test | Type |
|---|------|------|
| 1 | Register OpenAI provider (name, API key field, save) | Registry-only |
| 2 | Verify OpenAI appears in `/models` catalog | Registry-only |
| 3 | Register Anthropic/Claude provider | Registry-only |
| 4 | Register Google Gemini provider | Registry-only |
| 5 | Register Vertex AI provider (project ID + service account) | Registry-only |
| 6 | Register OpenRouter provider | Registry-only |
| 7 | Register Ollama provider → verify real `/api/tags` ping succeeds | Real call |
| 8 | Verify Ollama models appear in catalog | Real call |
| 9 | Verify LiteLLM fake provider (from setup) is listed | Registry-only |
| 10 | Deregister OpenRouter → confirm removed from catalog | Registry-only |

**`beforeAll`:** Read `.e2e-state.json` for providerId.  
**`afterAll`:** Nothing — teardown handles cleanup.

---

### `02-prompts.spec.ts`

**Scope:** Full prompt lifecycle — create, version, test, verify registry discoverability.

| # | Test |
|---|------|
| 1 | Create "e2e-support-prompt" via prompt builder (name, system text, team: e2e-team-alpha) |
| 2 | Save → verify appears in `/prompts` list |
| 3 | Open detail → edit system text → save as v2 → version selector shows v1 and v2 |
| 4 | Switch to v1 via version selector → verify older text is restored |
| 5 | Open test panel → send test input → verify response from LiteLLM fake |
| 6 | Search "e2e-support" in global search → prompt appears in results |
| 7 | Open agent builder → open registry picker for prompts → "e2e-support-prompt" is selectable |

---

### `03-tools.spec.ts`

**Scope:** Create tool, sandbox-execute it, verify registry availability.

| # | Test |
|---|------|
| 1 | Create "e2e-search-tool" via tool builder (name, description, JSON schema: `{query: string}`) |
| 2 | Save → verify appears in `/tools` list |
| 3 | Open tool detail → open sandbox runner → execute `{"query": "hello"}` → response panel appears |
| 4 | Sandbox: verify execution result is displayed (status, output, latency) |
| 5 | Search "e2e-search" in global search → tool appears |
| 6 | Open agent builder → tool picker → "e2e-search-tool" is selectable |

---

### `04-rag.spec.ts`

**Scope:** Create RAG index with pgvector backend, ingest a document, query it, verify registry availability.

| # | Test |
|---|------|
| 1 | Navigate to RAG builder → create "e2e-kb-docs" (pgvector backend, team: e2e-team-alpha) |
| 2 | Save → verify appears in RAG index list |
| 3 | Upload a small `.txt` file (< 1KB, plain text) |
| 4 | Wait for ingestion status → "ready" (poll with timeout 30s) |
| 5 | Run test search "hello" → verify at least 1 chunk returned |
| 6 | Open agent builder → knowledge base picker → "e2e-kb-docs" is selectable |

---

### `05-mcp-servers.spec.ts`

**Scope:** Register, view, and deregister MCP servers; verify agent builder integration.

| # | Test |
|---|------|
| 1 | Register "e2e-mcp-fetch" (command: `npx @modelcontextprotocol/server-fetch`, no auth) |
| 2 | Verify appears in `/mcp-servers` list |
| 3 | Open detail page → tools list loads (at least 1 tool visible) |
| 4 | Register "e2e-mcp-memory" (command: `npx @modelcontextprotocol/server-memory`) |
| 5 | Deregister "e2e-mcp-fetch" → verify removed from list |
| 6 | Verify "e2e-mcp-memory" still in list |
| 7 | Open agent builder → MCP picker → "e2e-mcp-memory" is selectable |

---

### `06-agents-nocode.spec.ts`

**Scope:** Create a fully-configured agent via the visual no-code builder; verify YAML round-trip; register.

**`beforeAll`:** Assert "e2e-support-prompt", "e2e-search-tool", "e2e-kb-docs", "e2e-mcp-memory" exist (from prior specs). If missing, seed via API.

| # | Test |
|---|------|
| 1 | Open `/agent-builder` → visual canvas loads |
| 2 | Set name "e2e-agent-nocode", framework: `claude_sdk`, team: `e2e-team-alpha` |
| 3 | Open registry picker → attach prompt "e2e-support-prompt" |
| 4 | Open registry picker → attach tool "e2e-search-tool" |
| 5 | Open registry picker → attach RAG "e2e-kb-docs" |
| 6 | Open registry picker → attach MCP "e2e-mcp-memory" |
| 7 | Set model: Ollama provider + first available local model |
| 8 | Toggle "View YAML" → verify `agent.yaml` contains all ref names |
| 9 | Toggle back to visual → canvas nodes preserved (round-trip fidelity) |
| 10 | Click Register → success toast → agent appears in `/agents` |

---

### `07-agents-lowcode.spec.ts`

**Scope:** Create agent via raw YAML editor; verify visual ↔ YAML reversibility; register.

| # | Test |
|---|------|
| 1 | Open `/agent-builder` → switch to YAML mode |
| 2 | Paste full valid `agent.yaml` for "e2e-agent-lowcode" (langgraph, all refs) |
| 3 | Click Validate → zero schema errors shown |
| 4 | Toggle Visual View → canvas renders nodes matching YAML refs |
| 5 | Make a UI change (add tag "e2e") → toggle back to YAML → tag appears in YAML |
| 6 | Click Register → success toast → agent appears in `/agents` |

---

### `08-agent-execution.spec.ts`

**Scope:** Execute both agents in the playground sandbox; verify chat, token display, model override.

**`beforeAll`:** Assert both agents exist; assert LiteLLM fake provider is available.

| # | Test |
|---|------|
| 1 | Open `/playground` → select "e2e-agent-nocode" |
| 2 | Send message "Hello" → assistant response appears |
| 3 | Token count badge visible on assistant message |
| 4 | Send "What can you help me with?" → conversation history maintained (2 exchanges shown) |
| 5 | Switch agent to "e2e-agent-lowcode" → new conversation starts (history cleared) |
| 6 | Override model in playground model selector → send message → response uses overridden model |

---

### `09-tracing.spec.ts`

**Scope:** Verify execution traces are recorded with spans, latency, token data, and are filterable.

**`beforeAll`:** Assert at least 2 playground runs exist (from spec 08).

| # | Test |
|---|------|
| 1 | Navigate to `/traces` → at least 2 traces listed |
| 2 | Open first trace → span tree renders (root span + at least 1 LLM call span) |
| 3 | LLM span shows latency in ms |
| 4 | LLM span shows prompt tokens + completion tokens |
| 5 | Filter by agent name "e2e-agent-nocode" → results scoped to that agent |
| 6 | Open trace detail → filter by date range (last 1 hour) → traces visible |

---

### `10-evals.spec.ts`

**Scope:** Create eval dataset, run evaluations against agents, view results, compare runs.

| # | Test |
|---|------|
| 1 | Navigate to `/eval-datasets` → create "e2e-eval-dataset" |
| 2 | Add 3 test cases (input + expected output text) |
| 3 | Save → verify dataset appears in list with "3 cases" count |
| 4 | Create eval run: agent "e2e-agent-nocode" + dataset "e2e-eval-dataset" → start |
| 5 | Wait for run status "completed" (poll 60s timeout) |
| 6 | Open run detail → score displayed per test case (pass/fail or numeric) |
| 7 | Create second eval run with "e2e-agent-lowcode" + same dataset |
| 8 | Navigate to eval comparison → select both runs → comparison table renders |

---

### `11-costs.spec.ts`

**Scope:** Verify token-based cost data flows from traces into the cost dashboard.

**`beforeAll`:** Assert playground + eval runs exist.

| # | Test |
|---|------|
| 1 | Navigate to `/costs` → overall spend chart loads with non-zero data |
| 2 | Filter by team "e2e-team-alpha" → chart updates |
| 3 | Filter by agent "e2e-agent-nocode" → agent-level token + cost breakdown visible |
| 4 | Token count in cost view matches token count in corresponding trace |
| 5 | Navigate to `/budgets` → create budget alert for "e2e-team-alpha" at $10 limit |
| 6 | Verify budget alert appears in list with correct team and threshold |

---

### `12-rbac.spec.ts`

**Scope:** Verify access control across all asset types for admin, member, and viewer roles.

**Uses:** `adminPage`, `memberPage`, `viewerPage` fixtures (separate browser contexts).

#### Prompts RBAC
| # | Role | Test |
|---|------|------|
| 1 | viewer | Cannot see Edit button on "e2e-support-prompt" |
| 2 | member | Can edit "e2e-support-prompt" (same team) |
| 3 | member | Cannot see/access prompts owned by "e2e-team-beta" |

#### Tools RBAC
| # | Role | Test |
|---|------|------|
| 4 | viewer | Sandbox runner button is absent/disabled on tool detail |
| 5 | member | Can open and execute sandbox runner |

#### RAG RBAC
| # | Role | Test |
|---|------|------|
| 6 | viewer | Upload button absent on "e2e-kb-docs" detail |
| 7 | member | Can upload a document to "e2e-kb-docs" |

#### MCP Servers RBAC
| # | Role | Test |
|---|------|------|
| 8 | viewer | MCP detail page is read-only (no deregister button) |
| 9 | admin | Deregister button visible and functional |

#### Agents RBAC
| # | Role | Test |
|---|------|------|
| 10 | viewer | Register/Deploy button absent on agent builder |
| 11 | member | Can register agent to "e2e-team-alpha" |
| 12 | member | Cannot assign agent to "e2e-team-beta" (team picker excludes it) |

#### Costs RBAC
| # | Role | Test |
|---|------|------|
| 13 | viewer | Costs page shows only "e2e-team-alpha" data |
| 14 | admin | Costs page shows all teams including "e2e-team-beta" |

#### Audit Log RBAC
| # | Role | Test |
|---|------|------|
| 15 | member | `/audit` redirects to 403/unauthorized page |
| 16 | admin | `/audit` loads with full event list |

#### Teams RBAC
| # | Role | Test |
|---|------|------|
| 17 | member | "Create Team" button absent on `/teams` |
| 18 | admin | "Create Team" button present and opens creation dialog |

---

## Test Count Summary

| Spec | Tests |
|------|-------|
| 01-providers | 10 |
| 02-prompts | 7 |
| 03-tools | 6 |
| 04-rag | 6 |
| 05-mcp-servers | 7 |
| 06-agents-nocode | 10 |
| 07-agents-lowcode | 6 |
| 08-agent-execution | 6 |
| 09-tracing | 6 |
| 10-evals | 8 |
| 11-costs | 6 |
| 12-rbac | 18 |
| **Total** | **96** |

---

## Dependency Order

```
global.setup
    ↓
01-providers  02-prompts  03-tools  04-rag  05-mcp-servers   ← parallel
                                    ↓
                    06-agents-nocode  ║  07-agents-lowcode    ← parallel (different agent names)
                                    ↓
                             08-agent-execution
                             ↙                ↘
                      09-tracing           10-evals           ← parallel
                             ↘                ↙
                              11-costs
                                   ↓
                              12-rbac (reads all assets)
                                   ↓
                            global.teardown
```

Specs 01–05 run in parallel. Specs 06–07 run in parallel (they create distinct agents). Specs 08–12 run sequentially — each depends on data produced by the previous group.

---

## Docker Prerequisites

Before running the suite, the following must be up:

```bash
docker compose -f deploy/docker-compose.yml up -d
# Wait for health checks:
#   postgres: pg_isready
#   redis: redis-cli ping
#   api: GET /health → 200
#   dashboard: GET / → 200
#   litellm: GET /health → 200
```

Ollama must be running locally (`ollama serve`) with at least one model pulled (`ollama pull llama3.2`).

---

## Environment Variables (`.env.e2e`)

```bash
PLAYWRIGHT_TEST_BASE_URL=http://localhost:3001
E2E_API_BASE_URL=http://localhost:8000
E2E_ADMIN_EMAIL=e2e-admin@test.local
E2E_ADMIN_PASSWORD=E2eAdmin123!
E2E_MEMBER_EMAIL=e2e-member@test.local
E2E_MEMBER_PASSWORD=E2eMember123!
E2E_VIEWER_EMAIL=e2e-viewer@test.local
E2E_VIEWER_PASSWORD=E2eViewer123!
OLLAMA_BASE_URL=http://localhost:11434
```

---

## What Is NOT Tested

- AWS / GCP cloud deployment (requires real cloud credentials + provisioning time)
- Real LLM calls for cloud providers (OpenAI, Claude, Gemini, Vertex, OpenRouter) — registry registration only
- Email notifications (no SMTP server in Docker stack)
- Mobile/responsive layout (Chromium desktop only)
- WebSocket/streaming responses beyond basic "response appears" assertion
