# Memory Platform — Working / Episodic / Semantic + Universal Tools

> **Status:** Design (not yet implemented). Tracked under epic `#TBD-E` (linked once filed).
> **Author:** AgentBreeder team, 2026-04-30.
> **Related design:** Sits alongside `docs/architecture/rag-platform.md` (#249), `docs/architecture/rag-tools.md` (#269), and the AgentOps lifecycle (`docs/architecture/agentops-lifecycle.md`, #243).

---

## 1. The problem

Track L (migrations 016/017) shipped basic memory persistence — `memory_configs`, `memory_messages`, `memory_entities` tables, an embedding column, and a `memory_manager.py` runtime helper. But it stops short of a complete memory platform:

1. **No tiered abstraction.** Working memory (within a session), episodic memory (cross-session events), and semantic memory (distilled facts) are blurred together. Different storage requirements get the same schema.
2. **No backend pluggability.** A team that wants Redis for working memory, pgvector for semantic, and Postgres for episodic has to fork.
3. **No cross-framework tools.** Each runtime has its own `memory_manager`. A Python LangGraph agent and a Node OpenAI Agents agent in the same workspace can't share memory the same way.
4. **No scope hierarchy.** Today memory is keyed by `(agent, session)`. Per-user memory across agents, per-team memory, and per-org memory don't exist as first-class scopes.
5. **No compaction or summarization.** Episodic memory grows unbounded. There's no "summarize the last 100 turns into a single semantic fact" pipeline.
6. **No retention or privacy policy.** GDPR-style "delete all memories belonging to this user" is operator-side scripting, not a tool call.
7. **No per-env parity.** A `memory.yaml` that uses Redis locally and ElastiCache + pgvector in prod requires hand-editing.
8. **No git lifecycle.** Memory configs are saved to the workspace DB, not git. There's no PR review for "this agent now stores per-user memory" — which is exactly the kind of change that needs review.

## 2. Goals and non-goals

### Goals

- Three explicit tiers: **working** (in-session), **episodic** (cross-session events), **semantic** (distilled facts).
- Pluggable backend abstraction per tier, reusing Epic B's `VectorStore` for the semantic layer.
- 6 canonical memory tools shipped as an MCP server (peer of RAG tools epic #270).
- Scope hierarchy: `session`, `agent`, `user`, `team`, `org`.
- Compaction & summarization as platform concerns (cron-driven via #199).
- Retention & privacy enforced server-side: `delete_on_request: true`, `max_age: 90d`, audit on every read/write/forget.
- Per-env parity (same `memory.yaml`, different backends per env).
- Full reuse of the AgentOps lifecycle (#244) — `memory.yaml` is git-backed, PR-reviewed, per-env promoted.

### Non-goals

- Custom embedders inside memory tools (use the index's `embedder` block — same pattern as RAG).
- Cross-org memory sharing.
- Differential privacy / synthetic memory anonymization (separate research effort).
- Memory-augmented training of custom models.

---

## 3. Three memory tiers

```
                         ┌─────────────────────────────────────────────────┐
                         │  Agent calls memory.recall("billing", "...")    │
                         └─────────────────────┬───────────────────────────┘
                                               │
                                               ▼
                         ┌─────────────────────────────────────────────────┐
                         │           Memory MCP server (epic E)             │
                         │                                                  │
                         │   ┌─────────────────────────────────────────┐  │
                         │   │ ACL → resolve scope → fan out to tiers  │  │
                         │   └─────────────────────────────────────────┘  │
                         │                                                  │
                         │  ┌─────────┐    ┌─────────┐    ┌─────────────┐ │
                         │  │ WORKING │    │EPISODIC │    │  SEMANTIC   │ │
                         │  │         │    │         │    │             │ │
                         │  │ Redis / │    │Postgres │    │ VectorStore │ │
                         │  │ memory  │    │  rows   │    │  (Epic B)   │ │
                         │  │         │    │+ graph  │    │             │ │
                         │  │  TTL    │    │ slice   │    │  retention  │ │
                         │  │  24h    │    │         │    │  + decay    │ │
                         │  └─────────┘    └─────────┘    └─────────────┘ │
                         │                                                  │
                         │  ┌────────────────────────────────────────────┐ │
                         │  │ Compaction cron — episodic → semantic     │ │
                         │  │ Decay cron — semantic score erosion       │ │
                         │  │ Retention cron — purge by max_age         │ │
                         │  └────────────────────────────────────────────┘ │
                         └─────────────────────────────────────────────────┘
```

### Working memory

- Within one session — last N turns, scratchpad, intermediate tool outputs
- Backend default: **process memory** for single-replica dev; **Redis** for multi-replica
- TTL: configurable (default 24h)
- Never embedded; raw text/JSON

### Episodic memory

- Cross-session events: "Alice cancelled order #1234 on March 12"
- Backend: **Postgres** for the event rows (ordered, indexed by `(scope, actor, timestamp)`); **graph slice** in Neo4j/Aura/Neptune for entity relationships extracted from events
- Retention: per-scope `max_age` (default 90d for `per_user`, indefinite for `per_team` / `per_org`)
- Embeddings optional — used only when a row gets summarized into semantic memory

### Semantic memory

- Distilled facts: "Alice prefers email over SMS", "Customer XYZ's support tier is enterprise"
- Backend: **vector store** (reuses Epic B's `VectorStore` Protocol — Chroma local, pgvector/Pinecone/etc. cloud)
- Retention: indefinite, with **decay scoring** — facts not retrieved in N days lose score; facts at score < threshold get pruned by retention cron
- The platform **owns the transition** from episodic to semantic via a compaction cron (see §6)

---

## 4. Memory tools (peer of RAG tools, ship as MCP)

Same pattern as #270. Single MCP server at `engine/tools/standard/memory_mcp/`, thin SDK wrappers in Python / TypeScript / Go.

| Tool | Purpose | ACL |
|---|---|---|
| `memory.recall(scope, query, k=5, tier=auto)` | Semantic search across memories. `tier=auto` queries semantic first, falls back to episodic. | `read` on scope |
| `memory.write(scope, content, tags={}, tier=episodic)` | Store an episode/fact. `tier=working` for short-term scratchpad; `tier=episodic` for persistence; `tier=semantic` for distilled facts | `write` on scope |
| `memory.forget(scope, doc_ids OR query)` | Privacy-aware deletion. Cascades across vector + episodic + working. Honors `delete_on_request: true` policy. | `write` on scope |
| `memory.summarize(scope, since=..., max_tokens=...)` | Async compaction — collapse N episodes into a semantic fact. Returns the new semantic doc id. | `write` on scope |
| `memory.list_scopes()` | Discovery. Returns scopes the calling agent has read access to. | filter |
| `memory.export(scope, format=json/jsonl)` | GDPR-style export of all memories in a scope. | admin or self-export |

Every result carries `{memory_id, scope, tier, source_event_id, score, metadata, written_at}` so the agent can cite recall.

---

## 5. Scope model

```yaml
# memory.yaml
name: customer-support-memory
description: Memory shared across customer-success agents
team: customer-success

scopes:
  - name: per_session              # working memory — auto-purged on session end
    backend:
      working: redis               # or 'memory' for single-replica
    ttl: 24h

  - name: per_user                 # cross-session per individual user
    backend:
      episodic: postgres
      semantic: pgvector           # reuses Epic B VectorStore
      graph: neo4j                 # for entity extraction (optional)
    retention:
      max_age: 90d
      delete_on_request: true      # GDPR-compliant
      decay:
        enabled: true
        half_life_days: 30
        prune_below_score: 0.1

  - name: per_team                 # team-shared learnings, anonymized
    backend:
      episodic: postgres
      semantic: pgvector
    retention:
      max_age: indefinite
      delete_on_request: true
    privacy:
      pii_redaction: true          # via guardrails (existing)

  - name: per_org                  # org-wide knowledge (admin-curated)
    backend:
      episodic: postgres
      semantic: pgvector
    retention:
      max_age: indefinite

# Per-env backend overrides (mirrors RAG platform)
environments:
  - name: dev
    overrides:
      per_user.backend.semantic: { type: chroma }
      per_user.backend.graph:    { type: neo4j, uri: bolt://localhost:7687 }
  - name: prod
    overrides:
      per_user.backend.semantic: { type: pgvector, dsn: secret://prod-pgvector }
      per_user.backend.graph:    { type: neo4j_aura, uri: secret://prod-aura }

compaction:
  schedule: "0 4 * * *"             # nightly (uses #199 cron)
  episodic_to_semantic:
    after_n_events: 100
    max_age: 30d
    embedder:
      model: text-embedding-3-large

# Same git lifecycle as agents (epic #244)
access:
  visibility: team
  allowed_callers:
    - team:customer-success
```

### Scope authorization

- **`per_session`** — auto-resolved by the runtime to the current session id; ACL is implicit (only the running agent + user)
- **`per_user`** — keyed by `actor_email`; only the user themselves + admin can read; users can self-export and self-delete (GDPR)
- **`per_agent`** — keyed by `agent_name`; only that agent + agent owner can read
- **`per_team`** — keyed by `team`; team members + admin can read
- **`per_org`** — keyed by `org`; admin-curated, all users can read

ResourcePermission ACL (migration 015) backs all of these — same primitive as agents/RAG.

---

## 6. Compaction & summarization

The platform owns the transition from episodic → semantic. A nightly cron job (using #199's daily-cron infra) runs per-scope:

```python
async def compact_scope(scope: MemoryScope, env: str) -> CompactionResult:
    """Roll up old episodic events into a single semantic fact."""
    cfg = scope.compaction.episodic_to_semantic
    cutoff = now() - timedelta(days=cfg.max_age_days)

    events = await EpisodicStore.list(
        scope=scope.name,
        env=env,
        before=cutoff,
        limit=cfg.after_n_events,
    )
    if len(events) < cfg.after_n_events:
        return CompactionResult(skipped=True, reason="not enough events")

    summary = await summarize_events(events, embedder=cfg.embedder)
    fact = SemanticFact(
        scope=scope.name,
        content=summary.text,
        embedding=summary.embedding,
        source_event_ids=[e.id for e in events],
        compacted_at=now(),
    )
    await SemanticStore.upsert([fact])
    if scope.compaction.archive_episodes:
        await EpisodicStore.archive([e.id for e in events])
    return CompactionResult(compacted=len(events), new_fact_id=fact.id)
```

Decay scoring runs on the same cron — facts not retrieved in N days lose score; facts below threshold get pruned by the retention cron.

---

## 7. Privacy & retention (first-class, server-enforced)

- `delete_on_request: true` makes `memory.forget` actually scrub from vector store (not soft-delete). Used for GDPR right-to-be-forgotten requests.
- Auto-purge cron honors `max_age` per-scope.
- Audit events on every read / write / forget / export. Audit row carries `actor`, `scope`, `tier`, `memory_id`, `delta_kind`.
- `memory.export` is the platform's GDPR Article 15 (right of access) endpoint — JSON / JSONL output of every memory in a scope.
- SOC 2 control coverage already lands via the compliance scanner (#208) — we add `memory_retention_enforced` and `memory_deletion_logged` controls.

---

## 8. Per-env parity

Same as RAG platform: `memory.yaml` declares `environments:` overrides. The MCP server reads `AGENTBREEDER_ENV` at startup, resolves the per-env backends, opens connection pools per (env, scope), and uses the env's per-env service principal (#248) for cloud creds.

The agent's call (`memory.recall("per_user", "...")`) is identical across envs. Local hits Redis + Postgres + Chroma; prod hits ElastiCache + RDS + pgvector — agent code never changes.

---

## 9. Lifecycle integration (reuses #244)

`memory.yaml` is a git-backed registry artifact. It follows the same `Save & Submit` → PR → approve → deploy → registry flow as agents and RAG indexes:

- Editing a scope's retention policy from `90d` → `1y` triggers a PR (these are reviewable changes, not silent edits)
- Adding a new scope is a PR
- Promotion from `dev` → `prod` re-runs any necessary backend setup (creates new tables, vector indexes, etc.)
- Per-env registries (#247) get rows for each `memory.yaml` deploy with `git_ref` + `deployed_by` stamps

This is the same point as the RAG platform: **memory inherits the lifecycle**. We do not build a parallel governance pipeline.

---

## 10. Migration plan

### Phase 1 — Backend abstractions
- `WorkingStore`, `EpisodicStore`, `SemanticStore` Protocols
- Refactor existing memory_messages / memory_entities behind them
- Land Redis as the first `WorkingStore` impl (Postgres fallback for single-replica dev)
- Point `SemanticStore` at Epic B's `VectorStore` Protocol — no new vector code

### Phase 2 — Memory MCP server
- Server scaffolding (stdio + HTTP/SSE), reuses sidecar passthrough infra
- 6 tools: recall, write, forget, summarize, list_scopes, export
- ACL middleware, scope resolution, audit emission

### Phase 3 — Compaction & retention
- Compaction cron (uses #199)
- Decay scoring + retention prune cron
- `delete_on_request` cascade across all three tiers

### Phase 4 — Lifecycle + per-env
- Extend `memory.yaml` schema (scopes, environments, retention, compaction, privacy)
- Wire into AgentOps lifecycle (#244): `Save & Submit` from dashboard, PR review, per-env promotion
- Per-env service principal binding (#248)

### Phase 5 — SDK wrappers
- Python (`from agenthub.memory import recall, write, forget, ...`)
- TypeScript (`@agentbreeder/sdk` / `memory`)
- Go (`sdk/go/agentbreeder/memory/`)

Each phase is independently shippable. v2.3 → v2.5 spans all five.

---

## 11. Open questions

1. **PII redaction default.** Should `per_team` and `per_org` scopes default to `pii_redaction: true` (using existing guardrails)? Probably yes for `per_team` and above; `per_user` keeps PII because that's the point.
2. **Cross-scope writes.** Should `memory.write` allow writing to multiple scopes atomically (e.g. an event that's both `per_user` and `per_team`)? Defer to v2 of the API; v1 is one scope per call.
3. **Conflict resolution.** Two replicas update the same semantic fact concurrently. Last-write-wins is the default; an `optimistic_concurrency: true` flag gates conflict detection. Defer fancy CRDTs.
4. **Embedding cost.** A naive compaction over 100 events per scope per day across 1k scopes is 100k embedding calls. Budget gate via `cost_events` table — defer to a follow-up issue.
5. **Migration of existing memory.** Migrations 016/017 already populated `memory_messages` / `memory_entities`. Phase 1 needs a backfill step that maps existing rows to the new tier model. Specify in the migration PR.
6. **Cross-scope queries.** `memory.recall("per_user")` returns only `per_user` memories. Should there be a `memory.recall(["per_user", "per_team"])` for layered context? Probably yes; defer the API surface to v2 of the recall tool.

---

## 12. What exists today that we keep

| Primitive | Status | Reuse |
|---|---|---|
| Migration 016 (`memory_persistence`) | Shipped | Tier 2 `EpisodicStore` builds on `memory_messages` |
| Migration 017 (`memory_phase2` — entities + embedding) | Shipped | Tier 3 `SemanticStore` uses the embedding column |
| `engine/runtimes/templates/memory_manager.py` | Shipped | Refactor to call the Memory MCP server |
| `engine/schema/memory.schema.json` | Shipped | Extend with scopes / environments / retention / compaction |
| `api/routes/memory.py` | Shipped | Routes proxy to the MCP server (same shape as RAG) |
| Sidecar (Track J) | Shipped | Memory MCP runs as another sidecar tool — no new networking |
| Daily-cron infra (#199) | Shipped | Compaction + decay + retention crons |
| AgentOps lifecycle (#244) | Designed | `memory.yaml` follows the same git → PR → approve → deploy flow |
| Multi-store abstraction (#251) | Designed | `SemanticStore` IS Epic B's `VectorStore` |
| Per-env registry (#247) | Designed | `memory_configs` rows get `git_ref` + `deployed_by` stamps |
| Per-env service principals (#248) | Designed | MCP server's connection pools assume the env's role |
| ResourcePermission ACL (migration 015) | Shipped | Scope authorization |

This epic adds **one MCP server + thin wrappers + backend abstractions**. The lifecycle, governance, security, and infra all come from already-designed work.

---

## 13. Out of scope

- Custom embedders inside memory tools (use the scope's `embedder`)
- Differential privacy / synthetic memory
- Multi-tenant org isolation beyond per-scope ACL
- Memory-augmented training (separate ML effort)
- Cross-region replication
