# Runtime Contract v1

**Status:** Stable (v1)
**Version:** `1`
**Last revised:** 2026-04-28
**Owners:** `engine/runtimes/`
**Companion artifact:** [`runtime-contract-v1.openapi.yaml`](./runtime-contract-v1.openapi.yaml)
**Tracks:** Track I — Polyglot SDKs (Go / Kotlin / Rust / .NET) — see issue #165

---

## 1. Status & Scope

### 1.1 What this document is

This is the **HTTP contract** that every AgentBreeder agent container exposes,
regardless of the language or framework it is written in. It is the single
machine-checkable interface between an agent runtime (built by
`engine/runtimes/`) and the rest of the AgentBreeder platform (the API,
sidecar, CLI, and other agents over A2A).

The contract is **frozen at v1** for the duration of the v1.x line. Additive,
non-breaking changes (new optional response fields, new optional headers, new
endpoints) MAY be made in v1 minor revisions. Breaking changes require v2.

### 1.2 What this contract covers

- HTTP endpoints exposed by every agent container
- Request and response JSON shapes for those endpoints
- Server-Sent Event (SSE) framing for `/stream`
- Authentication scheme
- Required and optional headers
- HTTP status code semantics
- The error envelope returned by the agent
- The split of responsibilities between the agent and the platform sidecar
- The mechanism by which an agent advertises which contract version it
  implements

### 1.3 What this contract explicitly does NOT cover

- **Deploy mechanics.** How the container is built, scheduled, scaled, or
  rolled out is the deployer's concern. See `engine/deployers/`.
- **Image format.** What is inside the container (Python vs Node vs Go vs
  Rust, base image, package manager) is the runtime builder's concern. See
  `engine/runtimes/`.
- **Framework integrations.** Whether the agent uses LangGraph, CrewAI,
  Vercel AI, Mastra, etc., is invisible at this layer. The framework's job is
  to satisfy the contract.
- **A2A inter-agent protocol.** A2A's JSON-RPC protocol layers on top of the
  agent's HTTP surface — see `engine/a2a/protocol.py`. The contract here only
  guarantees `/invoke` exists and accepts the documented body.
- **MCP.** The MCP server contract lives in `engine/schema/mcp-server.schema.json`
  and is a separate kind of container (`type: mcp-server`). MCP servers do
  not implement this contract.
- **The cross-platform API envelope** (`{data, meta, errors}`). That is the
  central API's response shape, not the agent's. See §4.6 for the
  agent-side error envelope and the rationale for the difference.

### 1.4 Audience

- Track I SDK authors (Go, Kotlin, Rust, .NET) who must generate compatible
  client and server code from this spec.
- Track J sidecar authors who proxy/instrument these endpoints.
- Anyone writing a custom (Tier 3) agent in an unsupported language and
  needing a target to comply with.

---

## 2. Endpoints — at a glance

| Method | Path                        | Auth   | Required | Purpose                                                  |
| ------ | --------------------------- | ------ | -------- | -------------------------------------------------------- |
| GET    | `/health`                   | open   | yes      | Liveness/readiness probe                                 |
| POST   | `/invoke`                   | bearer | yes      | Synchronous run                                          |
| POST   | `/stream`                   | bearer | yes      | Streaming run via SSE                                    |
| POST   | `/resume`                   | bearer | optional | Resume a paused (HITL) run — supported only by frameworks with checkpointing (LangGraph today) |
| GET    | `/openapi.json`             | open   | optional | Self-describing OpenAPI schema. Required for Tier 1; optional for Tier 2/3. |
| GET    | `/.well-known/agent.json`   | open   | optional | A2A agent card. Required when the agent is exposed for A2A; optional otherwise. |

Endpoints not listed here MUST NOT be assumed by callers. In particular,
`/cancel`, `/health/ready`, `/metrics`, `/mcp`, and `/runs/{id}` are **not**
part of v1 (see §10 Open Questions).

---

## 3. Authentication

### 3.1 Scheme

Bearer token via the `Authorization` header:

```
Authorization: Bearer <token>
```

### 3.2 Token source

The expected token is read from the environment variable `AGENT_AUTH_TOKEN`,
which is injected by the deployer at container startup.

- If `AGENT_AUTH_TOKEN` is **unset or empty**, the agent MUST disable auth
  (i.e. accept all requests). This is the local-dev path; do not require
  ceremony for `docker compose up`.
- If `AGENT_AUTH_TOKEN` is **set and non-empty**, the agent MUST require it on
  every request to a protected endpoint and MUST reject mismatches.

### 3.3 Protected vs open endpoints

| Endpoint                    | Auth required when `AGENT_AUTH_TOKEN` is set? |
| --------------------------- | --------------------------------------------- |
| `GET /health`               | NO — must always be reachable so cloud platform health probes (Cloud Run, ECS, Kubernetes liveness/readiness) work without credentials |
| `GET /.well-known/agent.json` | NO — agent card is public discovery metadata |
| `GET /openapi.json`         | NO — discovery and codegen target            |
| `POST /invoke`              | YES                                           |
| `POST /stream`              | YES                                           |
| `POST /resume`              | YES                                           |

### 3.4 Error responses

| Condition                                       | Status | Body                                                  |
| ----------------------------------------------- | ------ | ----------------------------------------------------- |
| Header missing or not `Bearer …`                | 401    | `{"detail": "Missing bearer token"}`                  |
| Header present but token does not match         | 403    | `{"detail": "Invalid bearer token"}`                  |

Note: the `{"detail": "..."}` shape comes from FastAPI's default error
serializer in the Python templates and was matched verbatim in the Node
templates. SDK clients SHOULD treat 401/403 as auth failures regardless of
body shape; bodies are advisory.

### 3.5 Token rotation

Token rotation is a deploy-time concern: the deployer redeploys the agent
with a new `AGENT_AUTH_TOKEN`. Agents MUST NOT support runtime rotation in v1.

---

## 4. Endpoint specifications

### 4.1 `GET /health`

**Auth:** open
**Purpose:** Liveness and readiness probe for cloud platforms and the platform health checker.

**Response — 200 OK:**
```json
{
  "status": "healthy",
  "agent_name": "customer-support-agent",
  "version": "1.0.0"
}
```

| Field        | Type    | Required | Notes                                                  |
| ------------ | ------- | -------- | ------------------------------------------------------ |
| `status`     | string  | yes      | One of `"healthy"` (loaded, ready) or `"loading"` (booting). The string `"ok"` is accepted as an alias for `"healthy"` for backward compatibility but new implementations MUST emit `"healthy"`. |
| `agent_name` | string  | yes      | The agent's slug name (matches `agent.yaml: name`).    |
| `version`    | string  | yes      | The agent's SemVer (matches `agent.yaml: version`).    |
| `framework`  | string  | no       | Optional framework hint, e.g. `"langgraph"`, `"vercel-ai"`. |

**Status semantics:**
- 200: container is reachable. `status: "healthy"` means agent is loaded and
  invoke is safe; `status: "loading"` means the container is up but the agent
  graph/object has not finished initializing yet — invoke will return 503.

**Note on Python/Node divergence at v0:** the Python templates emitted
`"healthy"`/`"loading"`; the current Node templates emit `"ok"` plus
`agent`/`framework` fields. v1 canonicalizes the Python shape (`status`,
`agent_name`, `version`); Node templates will be migrated to match. SDKs
SHOULD accept both `"ok"` and `"healthy"` as healthy.

### 4.2 `POST /invoke`

**Auth:** bearer
**Purpose:** Synchronous, single-shot agent run. Returns when the agent has
produced its final output (or paused at an interrupt — see "interrupted"
status).

**Request body:**
```json
{
  "input": "What is the status of order 123?",
  "session_id": "thread-abc-123",
  "config": { "configurable": { "user_id": "alice" } }
}
```

| Field        | Type                | Required | Notes                                                  |
| ------------ | ------------------- | -------- | ------------------------------------------------------ |
| `input`      | string \| object    | yes      | Free-form input. String for chat-style agents; object for graph-style agents (e.g. LangGraph `{ "messages": [...] }`). SDKs MUST support both. |
| `session_id` | string              | no       | Conversation/thread identifier. If the framework supports threading (LangGraph, Google ADK), it is honored; otherwise ignored. The agent generates and returns one if the caller does not provide it. |
| `config`     | object              | no       | Free-form, framework-specific config bag. Pass-through to the underlying framework's invoke `config` parameter. |
| `metadata`   | object              | no       | Free-form caller metadata (e.g. `{ "request_id": "...", "user_id": "..." }`). Reserved for use by the sidecar / the platform. |

**Response — 200 OK:**
```json
{
  "output": "Order 123 shipped on 2026-04-26.",
  "session_id": "thread-abc-123",
  "metadata": {
    "interrupted": false
  }
}
```

| Field        | Type                | Required | Notes                                                  |
| ------------ | ------------------- | -------- | ------------------------------------------------------ |
| `output`     | string \| object \| array | yes | The agent's response. Shape mirrors the framework: chat-style returns a string; graph-style returns the final state. |
| `session_id` | string              | no       | Echoed/generated thread id. Required when the agent honors `session_id`. |
| `metadata`   | object              | no       | Free-form, framework-specific. Notable optional keys: `interrupted` (bool — set when the run paused at a HITL breakpoint), `mode`, `output_schema_errors`. |

**Future-reserved fields** (sidecar-injected, see §6):
The following keys are reserved for the platform sidecar to attach to the
response after the agent returns. Agents MUST NOT populate them in v1; the
sidecar owns them.

| Reserved field | Type    | Owner   | Purpose                                  |
| -------------- | ------- | ------- | ---------------------------------------- |
| `trace_id`     | string  | sidecar | OpenTelemetry trace id                   |
| `tokens`       | object  | sidecar | `{input, output, total}` token counts    |
| `cost_usd`     | number  | sidecar | USD cost attributed to this invocation   |
| `model`        | string  | sidecar | Model id used for the invocation         |
| `latency_ms`   | integer | sidecar | End-to-end latency                       |

These fields are documented here so SDK codegen reserves space for them; until
Track J ships the sidecar, callers will not see them populated.

**Status codes:** see §5.

### 4.3 `POST /stream`

**Auth:** bearer
**Purpose:** Run the agent and stream incremental output as Server-Sent Events.

**Request body:** identical to `/invoke` (see §4.2).

**Response — 200 OK:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

**SSE event format.** Each event is one of two forms:

1. **Implicit `data:` events** — the JSON payload alone, used for token-by-token
   text streaming:

   ```
   data: {"delta": "Hello"}

   data: {"delta": " world"}
   ```

2. **Named events** with an `event:` line, used for structured updates such as
   tool calls, intermediate steps, and errors:

   ```
   event: step
   data: {"description": "search the web", "result": "..."}

   event: error
   data: {"error": "rate limited"}
   ```

**Defined event names for v1:**

| Event       | Payload shape                               | Emitted by                     | Required |
| ----------- | ------------------------------------------- | ------------------------------ | -------- |
| (implicit)  | `{"delta": "<text chunk>"}` or `{"text": "<text chunk>"}` | All frameworks producing text  | yes (text streaming) |
| `step`      | `{"description": "...", "result": "..."}`   | Frameworks with intermediate steps (CrewAI today) | optional |
| `tool_call` | `{"name": "...", "args": {...}}`            | Frameworks emitting tool-call deltas (reserved — emit when available) | optional |
| `error`     | `{"error": "<message>"}`                    | All — emitted before stream terminates if the run fails | optional |
| `result`    | `{"output": <any>}`                         | Frameworks that emit a final aggregated payload (CrewAI today) | optional |

**Stream terminator.** Every successful or failed stream MUST end with the
ASCII sentinel:

```
data: [DONE]

```

(Two newlines after `[DONE]`, per SSE framing.) The terminator is the SDK's
signal to close the stream.

**Note on Python/Node divergence at v0:** Python templates today emit a mix of
implicit `data:` events (Claude SDK: `{"text": "..."}`; OpenAI Agents:
`{"type": "...", "delta": "..."}`) and named `event:` events (CrewAI:
`event: step` / `event: result`). Node templates today emit only implicit
`data: {"delta": "..."}`. v1 canonicalizes the union: text MAY be carried in
either `delta` or `text` (SDKs MUST accept both); structured updates use named
events from the table above; every stream ends with `data: [DONE]`. Python
templates are conformant as-is; Node templates need no change for v1.

### 4.4 `POST /resume`

**Auth:** bearer
**Purpose:** Resume a previously paused run. Used by frameworks that support
checkpointing and human-in-the-loop (HITL) interrupts. Today only the
LangGraph runtime exposes `/resume`. All other agents MAY return 404 or 501.

**Request body:**
```json
{
  "thread_id": "thread-abc-123",
  "human_input": "Yes, ship it."
}
```

| Field         | Type   | Required | Notes                                  |
| ------------- | ------ | -------- | -------------------------------------- |
| `thread_id`   | string | yes      | The session/thread id of the paused run. |
| `human_input` | any    | yes      | The human response to feed back into the graph. |

**Response — 200 OK:** identical shape to `/invoke` response (§4.2).

**Status codes:**
- 200 — resumed and produced output
- 404 — `thread_id` not found
- 501 — runtime does not support `/resume`
- 503 — agent not loaded yet

### 4.5 `GET /openapi.json`

**Auth:** open
**Purpose:** Self-describing OpenAPI 3.x schema for the agent's HTTP surface.
Used by SDK codegen, the dashboard playground, and the validation tool.

Tier 1 runtimes (Python FastAPI, TypeScript Node) get this for free from
their HTTP framework. Tier 2 SDKs (Go, Kotlin, Rust, .NET) SHOULD generate
and serve a static OpenAPI document at this path. Tier 3 (BYO) MAY omit it.

**Self-advertised version.** The OpenAPI doc SHOULD include the contract
version in `info.x-agentbreeder-runtime-contract`:

```yaml
info:
  x-agentbreeder-runtime-contract: "1"
```

See also the `X-Runtime-Contract-Version` response header (§5.4).

### 4.6 Error envelope

When any protected endpoint fails, the agent SHOULD return a structured JSON
body:

```json
{
  "error": {
    "code": "AGENT_NOT_LOADED",
    "message": "Agent not loaded yet",
    "details": null
  },
  "trace_id": "0af7651916cd43dd8448eb211c80319c"
}
```

| Field                | Type    | Required | Notes                                                  |
| -------------------- | ------- | -------- | ------------------------------------------------------ |
| `error.code`         | string  | yes      | Stable, machine-readable code. SCREAMING_SNAKE_CASE.    |
| `error.message`      | string  | yes      | Human-readable summary.                                |
| `error.details`      | any     | no       | Free-form detail object.                               |
| `trace_id`           | string  | no       | OpenTelemetry trace id, when available (sidecar-injected). |

**Why the agent envelope differs from the platform envelope.** The
platform-side API uses `{ data, meta, errors }` (CLAUDE.md §API Conventions).
The agent envelope is intentionally terser — agents are leaf services that
return a single result and have no concept of paginated list metadata. SDK
clients that proxy through the platform API will see the platform envelope;
SDK clients that hit the agent directly (e.g. in-cluster A2A) will see the
agent envelope. Both are valid contracts at their respective layers.

**Backward-compat allowance.** Existing FastAPI agents return
`{"detail": "<message>"}` from `HTTPException`. v1 SDKs MUST tolerate this
shape on 4xx/5xx responses and treat it as `{"error": {"code": "UNSPECIFIED",
"message": "<detail>"}}`.

---

## 5. Headers

### 5.1 Required request headers

| Header                  | Where               | Notes                                  |
| ----------------------- | ------------------- | -------------------------------------- |
| `Authorization`         | protected endpoints | `Bearer <AGENT_AUTH_TOKEN>` (see §3)   |
| `Content-Type`          | POST endpoints      | `application/json`                     |

### 5.2 Optional request headers

| Header                | Purpose                                                  |
| --------------------- | -------------------------------------------------------- |
| `X-Trace-Id`          | Propagate an upstream OpenTelemetry trace id. Sidecar will use it as the parent span id when forwarding telemetry. |
| `X-Session-Id`        | Same as `session_id` in the body, but as a header. Body field wins on conflict. |
| `X-Idempotency-Key`   | Caller-supplied idempotency key. Reserved — agents MAY ignore in v1. |
| `X-Request-Id`        | Caller-supplied request id; logged by the sidecar.      |

### 5.3 Required response headers

| Header                       | Notes                                  |
| ---------------------------- | -------------------------------------- |
| `Content-Type`               | `application/json` (sync) or `text/event-stream` (stream) |
| `X-Runtime-Contract-Version` | Decimal contract version this agent implements. v1 servers MUST emit `1`. |

### 5.4 Optional response headers

| Header                       | Notes                                  |
| ---------------------------- | -------------------------------------- |
| `X-Trace-Id`                 | OTel trace id for the run (sidecar-set). |
| `X-Latency-Ms`               | End-to-end latency (sidecar-set).        |
| `Cache-Control`              | Required `no-cache` for `/stream`.       |
| `X-Accel-Buffering`          | Required `no` for `/stream` so reverse proxies do not buffer SSE. |

### 5.5 Versioning header

Every response from a v1 server MUST include
`X-Runtime-Contract-Version: 1`. SDK clients SHOULD validate this header and
warn if it is missing or higher than the version they were generated against.

---

## 6. Status codes

The agent uses HTTP status codes uniformly across endpoints.

| Status | Meaning                                                     | When                                                    |
| ------ | ----------------------------------------------------------- | ------------------------------------------------------- |
| 200    | Success                                                     | Sync run completed; stream opened; health OK.           |
| 202    | Accepted (reserved)                                         | Reserved for a future async-invoke endpoint. Not used in v1. |
| 400    | Bad Request                                                 | Malformed JSON, missing required field, unknown content-type. |
| 401    | Unauthorized                                                | Missing `Authorization` header on a protected endpoint. |
| 403    | Forbidden                                                   | `Authorization` token does not match `AGENT_AUTH_TOKEN`. |
| 404    | Not Found                                                   | Endpoint not implemented (e.g. `/resume` on a non-LangGraph agent), or thread/session id not found. |
| 422    | Unprocessable Entity                                        | Body parsed but failed validation (Pydantic/JSON-Schema). |
| 429    | Too Many Requests                                           | Reserved — sidecar-enforced rate limiting. The agent itself does not emit 429 in v1. |
| 500    | Internal Server Error                                       | Unhandled exception in the agent code. Body MUST be the error envelope (§4.6). |
| 501    | Not Implemented                                             | Endpoint exists in the spec but the runtime does not implement it (`/resume` outside LangGraph). |
| 503    | Service Unavailable                                         | Agent not loaded yet (startup not finished). Retry-After SHOULD be set. |

---

## 7. Sidecar interaction

### 7.1 What the sidecar (Track J) injects at runtime

When the platform sidecar is enabled (via the deployer injecting an
`agentbreeder-sidecar` container next to the agent container), the sidecar
sits in front of the agent and:

- Intercepts `/invoke` and `/stream`, forwards to the agent on `localhost`.
- Wraps every request in an OpenTelemetry span and forwards traces to the
  platform tracing endpoint.
- Counts tokens by parsing model SDK responses.
- Computes USD cost from token counts × the agent's resolved model price.
- Attaches `trace_id`, `tokens`, `cost_usd`, `model`, `latency_ms` to the
  agent's JSON response (or to the `done` SSE event).
- Records cost and audit events to the central API.
- Enforces guardrails (PII detection, content filtering).

### 7.2 What the agent must NOT do when the sidecar is active

When the environment variable `AGENTBREEDER_SIDECAR_ACTIVE=1` is set, the
agent runtime template MUST NOT:

- Open OpenTelemetry exporters or send traces directly.
- Compute its own token counts or USD cost.
- Send A2A calls directly to other agents — it MUST go through the sidecar's
  A2A proxy.
- Hit MCP servers directly — it MUST go through the sidecar's MCP proxy.

When the variable is absent (e.g. local dev), the agent MAY perform any of
the above directly. Tier 1 Python templates already do this conditionally.

### 7.3 Health check responsibility

`GET /health` is hit by the cloud platform's liveness probe, NOT by the
sidecar. The sidecar provides its own `/health` on a separate port (Track J
spec). The agent's `/health` MUST remain reachable at `:$PORT/health` and
MUST NOT be auth-gated.

---

## 8. OpenAPI artifact

The companion file
[`runtime-contract-v1.openapi.yaml`](./runtime-contract-v1.openapi.yaml) is
the machine-readable form of this contract. It is OpenAPI 3.1.

**Use cases:**
- Feed into `openapi-generator` to scaffold Tier 2 SDK servers (Go, Kotlin,
  Rust, .NET).
- Drive contract conformance tests (e.g. via `schemathesis`).
- Render an interactive playground in the dashboard.

**Source of truth.** The OpenAPI yaml and this markdown spec MUST agree. If
they diverge, the OpenAPI is canonical for shapes; the markdown is canonical
for prose, semantics, and SHOULD/MUST language.

---

## 9. Versioning policy

### 9.1 Version identifier

A single decimal integer: `1`, `2`, …. The version is exposed three ways:

1. The response header `X-Runtime-Contract-Version` (§5.5) — runtime check.
2. `info.x-agentbreeder-runtime-contract` in `/openapi.json` (§4.5) — discovery.
3. The path-stable filename `engine/schema/runtime-contract-v<N>.md` — repo identity.

### 9.2 What is non-breaking (v1.x)

- Adding a new optional field to a request or response.
- Adding a new optional header.
- Adding a new endpoint.
- Adding a new SSE event name.
- Documenting an existing de-facto behavior.

### 9.3 What is breaking (requires v2)

- Removing or renaming a field or endpoint.
- Changing a field's type (e.g. string → object).
- Changing the auth scheme.
- Changing the SSE terminator or framing.
- Changing the meaning of an existing status code.

### 9.4 How v2 will be added

When v2 ships, agents may serve v1 and v2 simultaneously. The version is
selected by the request header `X-Runtime-Contract-Version: 2`. Agents that
implement only one version MUST reject mismatched versions with 400. The
version is per-request, not per-deployment.

The Track I SDKs are codegen targets for v1 only; an SDK upgrade is required
to consume v2.

---

## 10. Compliance & validation (`agentbreeder validate-contract`)

A future CLI command will check that a built agent image conforms to this
contract end-to-end. Spec only — implementation is out of scope here.

```bash
agentbreeder validate-contract <image-or-url> \
    --version 1 \
    --token "$AGENT_AUTH_TOKEN" \
    [--strict]
```

Behavior:

1. Boot the image (or accept a running URL).
2. Hit `GET /health`; assert 200 and shape (§4.1).
3. Hit `GET /openapi.json` (if present); assert it advertises
   `x-agentbreeder-runtime-contract: "1"`.
4. Send a synthetic `POST /invoke`; assert 200 and shape.
5. Send a synthetic `POST /stream`; assert SSE framing and `[DONE]` terminator.
6. Probe `POST /resume` with an empty thread; assert 200 / 404 / 501 only.
7. Probe auth: missing token returns 401; bad token returns 403; `/health`
   stays open.
8. With `--strict`, also assert the `X-Runtime-Contract-Version: 1` header
   and the structured error envelope (§4.6).

A pass-fail report is printed; CI gates Tier 2 SDKs on it.

---

## 11. Reference implementations

The following Tier 1 runtime templates already conform to v1 (with the minor
divergences noted in §4):

| Language   | Framework                    | File                                                                |
| ---------- | ---------------------------- | ------------------------------------------------------------------- |
| Python     | LangGraph                    | `engine/runtimes/templates/langgraph_server.py`                     |
| Python     | OpenAI Agents SDK            | `engine/runtimes/templates/openai_agents_server.py`                 |
| Python     | CrewAI                       | `engine/runtimes/templates/crewai_server.py`                        |
| Python     | Claude SDK (Anthropic)       | `engine/runtimes/templates/claude_sdk_server.py`                    |
| Python     | Google ADK                   | `engine/runtimes/templates/google_adk_server.py`                    |
| Python     | Custom (BYO)                 | `engine/runtimes/templates/custom_server.py`                        |
| TypeScript | LangChain.js                 | `engine/runtimes/templates/node/langchain_js_server.ts`             |
| TypeScript | OpenAI Agents TS             | `engine/runtimes/templates/node/openai_agents_ts_server.ts`         |
| TypeScript | Custom Node                  | `engine/runtimes/templates/node/custom_node_server.ts`              |
| TypeScript | Vercel AI / Mastra / DeepAgent / MCP | `engine/runtimes/templates/node/{vercel_ai,mastra,deepagent,mcp_ts,mcp_py}_server.ts` |
| Shared TS  | Auth + agent card helpers    | `engine/runtimes/templates/node/_shared_loader.ts`                  |

Track I SDKs (Go, Kotlin, Rust, .NET) will be generated from
`runtime-contract-v1.openapi.yaml` and live under `engine/runtimes/templates/<lang>/`.

---

## 12. Open questions

These were considered for v1 and **deferred** with a documented default. Each
becomes a candidate for v1.x (additive) or v2 (breaking).

| # | Question | Current default (v1) | Where it would land |
| - | -------- | -------------------- | ------------------- |
| 1 | Do we need `POST /cancel`? | **No.** Long-running runs are out of scope for v1. Callers cancel by closing the HTTP connection. | v1.x additive if/when async-invoke ships |
| 2 | Split `/health` into `/health` (liveness) and `/health/ready` (readiness)? | **No.** `status: "healthy"` vs `"loading"` carries readiness inline. Cloud Run / k8s probes treat 200 as live; the body distinguishes loading. | v1.x additive — `/health/ready` would be added without removing `/health` |
| 3 | Cookie vs header for session id? | **Header (and body field).** Cookies are ill-suited for service-to-service traffic. | Frozen — won't change before v2 |
| 4 | Should the agent emit its own cost/tokens before the sidecar exists? | **No.** The reserved fields (`trace_id`, `tokens`, `cost_usd`, `model`, `latency_ms`) are sidecar-owned. Until Track J ships, callers will not see them populated. Letting the agent fill them invites drift. | Frozen for v1; sidecar fills them in Track J |
| 5 | Pin a single SSE text-delta key (`delta` vs `text`)? | **Both accepted.** New runtimes SHOULD emit `delta`. SDKs MUST accept both. | v2 may pin to one |
| 6 | Native MCP endpoint on the agent (`POST /mcp`)? | **Out.** MCP servers are a separate container type; agents do not implement MCP themselves. | Re-evaluate when bidirectional MCP-on-agent is needed |
| 7 | Idempotency for `/invoke`? | **Reserved.** `X-Idempotency-Key` is reserved but not enforced in v1. | v1.x — sidecar-enforced |
| 8 | Pluralization of `/resume` (e.g. `/runs/{id}:resume`)? | **No.** v1 keeps the flat `POST /resume` shape; resource-style URLs would imply runs are first-class platform objects, which they are not yet. | v2 candidate |
| 9 | Required vs optional status string canonicalization (`"ok"` vs `"healthy"`)? | **`"healthy"` is canonical, `"ok"` is accepted.** Node templates emit `"ok"` today; will be migrated. | v1.x — Node template patch |
| 10 | Does the agent expose `/.well-known/agent.json` even when A2A is disabled? | **Yes when A2A is the deploy target; otherwise optional.** Today only the Node templates emit it; Python templates will gain it via the A2A server module. | v1.x additive |

---

## 13. Change log

| Date       | Version | Change                                       |
| ---------- | ------- | -------------------------------------------- |
| 2026-04-28 | 1.0.0   | Initial spec — codifies current Tier 1 behavior. |
