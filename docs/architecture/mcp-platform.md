# MCP Platform — Internal Catalog + External Registration + Marketplace

> **Status:** Design (not yet implemented). Tracked under epic `#TBD-F` (linked once filed).
> **Author:** AgentBreeder team, 2026-04-30.
> **Related design:** Sits alongside `docs/architecture/rag-tools.md` (#269), `docs/architecture/memory-platform.md` (this commit), and the AgentOps lifecycle (`docs/architecture/agentops-lifecycle.md`, #243).

---

## 1. The problem

Today AgentBreeder treats MCP as a single homogeneous concept — `connectors/mcp_scanner/` discovers servers, `api/routes/mcp_servers.py` registers them, `engine/mcp/packager.py` ships them, the Track-J sidecar passes through traffic at `localhost:9090/mcp/<server>`. That works for the simplest case, but the platform stops short of a real MCP story:

1. **No internal/external distinction.** The platform ships some MCPs (RAG #270, Memory Epic E) AND lets users bring third-party MCPs. Today both flow through the same registration path with no policy distinction.
2. **No marketplace.** Users can't browse community MCPs from the dashboard. The existing `/marketplace` page (templates) doesn't include them.
3. **No per-env routing.** A `dev` agent should hit a mock MCP; `prod` should hit the real one. The registry holds a single `(name, url)` row, not N rows per env.
4. **No sandbox policy.** External MCPs run with the sidecar's full network egress. There's no per-server allowlist for outbound calls or filesystem access.
5. **No health & cost telemetry per server.** When an external MCP starts failing, we have no per-server status board. When it costs money (via downstream LLM calls), the cost isn't attributed to the calling agent.
6. **No git lifecycle.** Adding/changing an MCP is a `POST /api/v1/mcp_servers` call. That's exactly the kind of supply-chain change that needs PR review.
7. **No auth scheme uniformity.** Each MCP has its own auth flow; the platform doesn't standardize bearer / OAuth / mTLS / API-key.
8. **No discoverability for internal MCPs.** Once we ship 5+ internal servers (RAG, memory, registry, sandbox, A2A), users need a clean catalog page to know what's available out of the box.

## 2. Goals and non-goals

### Goals
- Clear taxonomy: **internal MCPs we ship** (RAG, memory, registry, sandbox, A2A) vs **external MCPs the user brings** (third-party, marketplace, org-internal).
- Per-env routing: same `mcp_servers` ref resolves differently in dev vs prod.
- Sandbox policy as a first-class field on every external MCP — egress allowlist, filesystem mode, resource limits.
- Health probes + per-server cost telemetry via the existing `cost_events` and audit infra.
- ACL via ResourcePermission — `read` (call any tool on the server) and `admin` (register/update/delete the server entry).
- Git lifecycle reuse from #244 — `mcp.yaml` is a registry artifact, PR-reviewed.
- Marketplace integration — extend the existing `/marketplace` page to include MCPs.
- Auth schemes standardized: `bearer`, `oauth2`, `mtls`, `api_key`, `none`. All credentials in the workspace secrets backend.

### Non-goals
- A bespoke MCP runtime. We use the upstream MCP protocol verbatim.
- Dynamic / runtime tool registration (MCP servers can re-emit their manifest at runtime; we cache it). Hot-add of brand new servers without a registration step is out.
- Cross-org MCP sharing.

---

## 3. Taxonomy

```
                ┌─────────────────────────────────────────────────────────┐
                │                    MCP SERVERS                          │
                │                                                          │
                │   ┌─────────────────────┐    ┌─────────────────────┐  │
                │   │     INTERNAL        │    │      EXTERNAL       │  │
                │   │  (we ship)          │    │   (user brings)     │  │
                │   │                     │    │                     │  │
                │   │  rag-mcp (#270)     │    │ Marketplace browse  │  │
                │   │  memory-mcp (Epic E)│    │ Direct CLI register │  │
                │   │  registry-mcp       │    │ Auto-detect scanner │  │
                │   │  sandbox-mcp        │    │                     │  │
                │   │  a2a-mcp            │    │ Org-internal        │  │
                │   │                     │    │ Third-party / SaaS  │  │
                │   │  always available   │    │ per-workspace opt-in│  │
                │   │  bundled in image   │    │ explicit registration│  │
                │   └─────────────────────┘    └─────────────────────┘  │
                │             │                          │                │
                │             └──────────┬───────────────┘                │
                │                        ▼                                 │
                │     ┌──────────────────────────────────────────┐        │
                │     │           MCP REGISTRY                    │        │
                │     │                                            │        │
                │     │  per-server row                           │        │
                │     │   ├─ name, kind (internal | external)     │        │
                │     │   ├─ per-env URL + auth (workspace secret)│        │
                │     │   ├─ sandbox policy                       │        │
                │     │   ├─ health probe config                  │        │
                │     │   ├─ ResourcePermission ACL               │        │
                │     │   ├─ cost attribution rules               │        │
                │     │   └─ git_ref / deployed_by / env stamps   │        │
                │     └──────────────────────────────────────────┘        │
                └─────────────────────────────────────────────────────────┘
```

### Internal catalog (we ship)

Bundled with every AgentBreeder install. Versioned (semver), pinnable in `agent.yaml`. No registration step needed — they're auto-attached when an agent declares them.

| Server | Tools | Status | Notes |
|---|---|---|---|
| **rag-mcp** | 8 RAG tools (#270) | Designed | Ships with Epic D |
| **memory-mcp** | 6 memory tools (Epic E) | Designed | Ships with Epic E |
| **registry-mcp** | `list_agents`, `get_prompt`, `find_tool`, `get_eval`, `find_kb` | NEW (this epic) | Read-only registry queries; ACL-filtered |
| **sandbox-mcp** | `python.exec`, `js.exec`, `shell.exec` | NEW (this epic) | Safe code execution with policy (CPU / memory / network egress) |
| **a2a-mcp** | `agent.invoke`, `agent.list`, `agent.card` | NEW (this epic) | Cross-agent calls via JSON-RPC; extends scaffolding under #205 |

### External MCPs (three discovery paths)

1. **Direct register** (CLI or API):
   ```
   agentbreeder mcp register \
     --name slack \
     --url https://mcp.slack.example.com \
     --transport http_sse \
     --auth secret://slack-token \
     --env prod
   ```
2. **Marketplace browse** (dashboard `/marketplace`):
   - Existing `/marketplace` page already exists for templates
   - Extend it with an "MCP Servers" tab showing community-vetted MCPs
   - Each entry has author + reviews + auth scheme + sandbox profile
   - One-click install (with explicit consent on the auth + sandbox manifest)
3. **Auto-detect scanner** (extends `connectors/mcp_scanner/`):
   - Scans Docker compose stacks, K8s services, `~/.claude.json`
   - Surfaces detected MCPs in the dashboard with "Register?" CTA
   - Never auto-registers; always requires explicit consent

---

## 4. `mcp.yaml` schema (NEW)

```yaml
name: zendesk
description: Customer support MCP for Zendesk
kind: external                          # internal | external | marketplace
team: customer-success
owner: alice@company.com

transport: http_sse                     # stdio | http_sse | http
auth:
  scheme: bearer                        # bearer | oauth2 | mtls | api_key | none
  token: secret://zendesk-token

# Per-env routing
environments:
  - name: dev
    url: http://localhost:8089
    auth: { scheme: none }
  - name: staging
    url: https://mcp-staging.zendesk.example.com
    auth: { scheme: bearer, token: secret://staging-zendesk-token }
  - name: prod
    url: https://mcp-prod.zendesk.example.com
    auth: { scheme: bearer, token: secret://prod-zendesk-token }

# Sandbox policy
sandbox:
  egress_allowlist:
    - "*.zendesk.com"
    - "api.zendesk.com"
  filesystem: read-only                 # read-only | none | tmpfs
  resource_limits:
    cpu_millicores: 500
    memory_mb: 512
    timeout_per_call_ms: 30000

# Health probe
health:
  endpoint: /health
  interval: 60s
  failure_threshold: 3                  # 3 failures → mark unhealthy + page

# Cost attribution
cost:
  attribute_to: caller                  # caller | server_owner
  upstream_model_meter: true            # extract usage from MCP responses

# Tool ACL (per-tool, optional override of server-level ACL)
tool_overrides:
  - name: zendesk.create_ticket
    required_role: deployer

# Server-level ACL via ResourcePermission
access:
  visibility: team
  allowed_callers:
    - team:customer-success
    - team:engineering

# Marketplace metadata (only for kind=marketplace)
marketplace:
  publisher: zendesk
  publisher_verified: true
  reviews_url: https://github.com/agentbreeder/marketplace/issues?label=mcp:zendesk
```

The schema is identical for internal MCPs except `kind: internal`, no `marketplace:` block, and the platform owns the `auth.token` secret.

---

## 5. Sandbox policy

Every external MCP runs inside the sidecar's existing tool-runner sandbox (already shipped) with the policy from `mcp.yaml.sandbox`:

- **`egress_allowlist`** — outbound connections allowed only to listed domains. Enforced at the sidecar's HTTP egress proxy. A `slack` MCP can't accidentally exfiltrate to `evil.example.com`.
- **`filesystem`** — `read-only` mounts the workspace's tools dir read-only; `none` denies all FS access; `tmpfs` mounts a per-call ephemeral RAM volume for sandbox-mcp's code execution.
- **`resource_limits`** — CPU / memory caps via cgroups; per-call timeout enforced by the runtime.
- **Internal MCPs** default to `egress_allowlist: ["*"]` + `filesystem: read-write` because they're trusted; the policy lives in their `mcp.yaml` for transparency.

A failing sandbox check returns `403 Sandbox policy violation` from the sidecar with an audit event `mcp.sandbox_violation` carrying the server name + violation kind.

---

## 6. Health & cost telemetry

### Health
- Sidecar pings each registered MCP's `health.endpoint` at the configured `health.interval`
- After `failure_threshold` consecutive failures, the registry's `mcp_servers.status` flips to `unhealthy`
- Dashboard `/mcp-servers` page surfaces a per-server status badge (mirrors how `/providers` already shows provider health)
- An auto-incident gets created via `IncidentService` (#207) when an `unhealthy` MCP is referenced by a deployed prod agent

### Cost
- Every MCP tool call emits a `cost_events` row with `(actor_email, agent_name, mcp_server, tool_name, duration_ms, status)`
- For MCPs that proxy LLM calls (an MCP that itself hits Anthropic / OpenAI), the response carries usage tokens; the sidecar parses and attributes
- `attribute_to: caller` (default) bills the calling agent's team; `attribute_to: server_owner` bills the MCP owner's team — useful for shared internal MCPs

---

## 7. Lifecycle integration (reuses #244)

`mcp.yaml` is a registry artifact. Same `Save & Submit` flow as agents. Same `pr_approval_state` (#245). Same per-env promotion (#246).

- Adding a new external MCP is a PR ("we now trust `slack-mcp` from publisher X") — explicitly reviewable
- Changing `sandbox.egress_allowlist` is a PR — reviewers see the diff in egress policy
- Promoting from `dev` to `prod` requires the env's approver count + eval gate (in this case, an MCP-conformance eval that makes sure the server actually serves the manifest it claimed)
- Per-env service principals (#248) handle cloud creds for MCPs that talk to AWS/GCP/Azure backends

The dashboard `/mcp-servers` page becomes the editor: list, create, edit, view health, view cost. Every action goes through the lifecycle.

---

## 8. Marketplace integration

The existing `/marketplace` page (templates) gets a second tab: **MCP Servers**. Listings carry:

- Name, description, publisher (verified or unverified)
- Auth scheme + sandbox profile (visible up front so users know what they're consenting to)
- Reviews + install count
- Source link (GitHub repo / docs)
- Categories (data, comms, productivity, dev tools, etc.)

`POST /api/v1/marketplace/mcps/<id>/install` does:
1. Renders `mcp.yaml` from the listing into the user's repo (creates a PR — reuses #244)
2. The PR diff shows everything the MCP declares: tools, auth, sandbox, env routing
3. User reviews + approves; merge triggers dev install
4. Same promote flow to staging / prod

This is the SECURE way to install — every install is git-tracked + reviewed. No silent updates.

---

## 9. Migration plan

### Phase 1 — Schema + lifecycle
- `mcp.yaml` schema landed
- `mcp_servers` registry table extended with per-env URL/auth, sandbox policy, health config, cost attribution
- Wire into AgentOps lifecycle (#244): `Save & Submit`, PR review, per-env promote
- Audit events: `mcp.registered`, `mcp.installed`, `mcp.uninstalled`, `mcp.sandbox_violation`

### Phase 2 — Internal MCP catalog
- `registry-mcp` — 5 read-only tools
- `sandbox-mcp` — `python.exec`, `js.exec`, `shell.exec` with policy
- `a2a-mcp` — extends scaffolding from #205
- (`rag-mcp` ships with epic #270, `memory-mcp` with Epic E — both already designed)

### Phase 3 — External MCP infrastructure
- CLI: `agentbreeder mcp register / list / health / uninstall`
- Auto-detect scanner (extends `connectors/mcp_scanner/`)
- Health probe runner (cron-based, reuses #199 infra)
- Per-server cost attribution

### Phase 4 — Sandbox policy enforcement
- Egress allowlist via sidecar proxy
- Filesystem modes via container mount
- Resource limits via cgroups
- Audit on every violation

### Phase 5 — Marketplace
- Extend `/marketplace` page with MCP Servers tab
- Listing schema, review/rating system (reuse template marketplace's review primitives)
- One-click install via PR generation
- Publisher verification flow

Each phase is independently shippable. v2.3 → v2.5 spans all five.

---

## 10. Open questions

1. **Default sandbox for internal MCPs.** Should `internal` default to permissive (`*` egress) or be expected to declare allowlist too? Probably the latter — even internal MCPs should declare egress for least-privilege. Defer the policy to per-server `mcp.yaml`.
2. **Marketplace verification.** Who verifies a publisher? Initially manual review by AgentBreeder team; automated checksumming + provenance attestation is v2.
3. **Backwards compat.** Existing `mcp_servers` rows lack per-env URLs and sandbox policy. Migration backfills them with the existing single URL into all envs and `sandbox: { egress_allowlist: ["*"] }` (with a follow-up audit recommendation).
4. **Auth refresh for OAuth.** OAuth2 tokens expire. The sidecar needs a refresh-token flow keyed by `(workspace, mcp_server, user)`. Reuse the existing OAuth refresher when it lands for RAG loaders (#250 sub-issues).
5. **Tool-level vs server-level ACL.** A user has `read` on the `slack` MCP but should not be able to call `slack.send_dm`. `tool_overrides:` in the `mcp.yaml` schema covers this; default is to inherit server ACL.
6. **Internal MCP versioning.** When the platform ships a new version of `rag-mcp`, agents pinned to v1.x should keep working. Need a side-by-side install model + a deprecation path.

---

## 11. What exists today that we keep

| Primitive | Status | Reuse |
|---|---|---|
| `connectors/mcp_scanner/` | Shipped | Auto-detect scanner extends this |
| `engine/mcp/packager.py` | Shipped | Internal MCP image build |
| `api/routes/mcp_servers.py` | Shipped | Extend with per-env / sandbox / health fields |
| `registry/mcp_servers.py` | Shipped | Extend with the same |
| Sidecar (Track J) — MCP passthrough | Shipped | All servers route through the sidecar |
| Sidecar tool-runner sandbox | Shipped | Sandbox policy enforcement plugs in here |
| Workspace secrets backend (Track K) | Shipped | All MCP auth tokens live here |
| `cost_events` table | Shipped | Per-server cost attribution |
| `audit_log` | Shipped | New event types: `mcp.installed`, `mcp.sandbox_violation`, `mcp.health_state_changed` |
| `IncidentService` (#207) | Shipped | Auto-create incidents on prod-MCP unhealthy |
| `/marketplace` page | Shipped (templates) | Extend with MCP Servers tab |
| AgentOps lifecycle (#244) | Designed | `mcp.yaml` follows the same flow |
| Per-env service principals (#248) | Designed | MCPs that need cloud creds assume env role |
| Daily cron infra (#199) | Shipped | Health probes + cost rollups |

This epic adds **3 internal MCP servers + lifecycle integration + sandbox enforcement + marketplace tab**. Most of the security and lifecycle pieces come from already-designed work.

---

## 12. Out of scope

- Hot-add of brand-new MCPs without a registration step
- Cross-org MCP sharing
- Custom MCP transport implementations beyond stdio / HTTP / SSE
- MCP-to-MCP composition / piping (orchestration belongs in agents)
