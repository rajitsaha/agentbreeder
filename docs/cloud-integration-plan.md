# AgentBreeder OSS — Cloud Integration Plan

**Date:** 2026-04-18  
**Purpose:** Documents all OSS modules that must be built to power [AgentBreeder Cloud](https://github.com/agentbreeder/agentbreeder-cloud).  
**Rule:** Every capability goes into OSS first. Cloud adds managed hosting, multi-tenancy, and billing on top.

Full architecture: [agentbreeder-cloud/docs/superpowers/specs/2026-04-18-north-star-architecture.md](https://github.com/agentbreeder/agentbreeder-cloud/blob/main/docs/superpowers/specs/2026-04-18-north-star-architecture.md)

---

## Why OSS First

AgentBreeder Cloud is an open-core product. The engine, RAG pipeline, eval framework, agent guide, and serving layer all live here so that:

- Self-hosters get the full capability without needing Cloud
- Cloud is a thin managed layer — not a fork
- Enterprise trust comes from OSS auditability
- Community contributions improve Cloud automatically

---

## Module Build Order

```
agentbreeder.rag                  ← document ingestion + vector RAG
    │
    ├── agentbreeder.rag.graph    ← GraphRAG (knowledge graph layer on top of RAG)
    │
agentbreeder.connectors.db        ← SQL/NoSQL query tool builder
    │
agentbreeder.eval.online          ← live response scoring
agentbreeder.eval.offline         ← golden dataset regression runner
    │
agentbreeder.guide                ← spec → LLM → agent config generator
agentbreeder.serving              ← per-agent REST endpoint server
    │
agentbreeder.sessions             ← session checkpointing + long-running agents
agentbreeder.memory               ← long-term cross-session memory bank
agentbreeder.engine.spawner       ← dynamic subagent spawning at runtime
```

`agentbreeder.rag` is the critical-path dependency — it unblocks GraphRAG, Agent Guide, and the RAG Builder in Cloud. Build it first.

---

## Module Specs

### M-C1 · `agentbreeder.rag` — Document RAG Pipeline

**ROADMAP milestone:** v2.1  
**Cloud unblocks:** RAG Builder (Phase 2), Agent Guide (Phase 3)  
**Cloud issues:** [#14](https://github.com/agentbreeder/agentbreeder-cloud/issues/14)

```
agentbreeder/rag/
  ingestion/
    pdf.py          # PyMuPDF → text extraction
    spreadsheet.py  # openpyxl + pandas → tabular text
    web.py          # Playwright headless → text extraction
    database.py     # SQLAlchemy row → chunk
  chunking/
    semantic.py     # sentence-transformers sliding window (~512 tokens)
    fixed.py        # token-based with overlap
    tabular.py      # one chunk per row (for spreadsheets/DB tables)
  embedding/
    openai.py       # text-embedding-3-small / large
    google.py       # text-embedding-004
    ollama.py       # local model
  store/
    pgvector.py     # Cloud SQL pgvector store
    base.py         # abstract interface
  retriever.py      # similarity search → top-K chunks with metadata
  tool.py           # rag_search tool auto-injected into agent tool bridge
```

**New deps:** `pymupdf`, `openpyxl`, `pandas`, `sentence-transformers`, `pgvector`

**Acceptance criteria:**
- PDF, XLSX, CSV, DOCX, web URL ingestion all produce chunked text
- Semantic and fixed-size chunking correct for a 100-page PDF
- Embeddings written to and retrieved from pgvector
- `retriever.py` returns top-K chunks with source metadata (file, page, score)
- `tool.py` is compatible with all 6 runtimes via `tool_bridge.py`
- Unit tests for all ingestion types + retrieval on a test corpus

---

### M-C2 · `agentbreeder.rag.graph` — GraphRAG

**ROADMAP milestone:** v2.2  
**Cloud unblocks:** Graph Explorer UI, GraphRAG search in Agent Builder  
**Cloud issues:** [#50](https://github.com/agentbreeder/agentbreeder-cloud/issues/50) [#51](https://github.com/agentbreeder/agentbreeder-cloud/issues/51) [#52](https://github.com/agentbreeder/agentbreeder-cloud/issues/52) [#53](https://github.com/agentbreeder/agentbreeder-cloud/issues/53)  
**Full spec:** [2026-04-18-graphrag-design.md](https://github.com/agentbreeder/agentbreeder-cloud/blob/main/docs/superpowers/specs/2026-04-18-graphrag-design.md)

**Why:** Naive vector RAG fails on multi-hop queries (*"all decisions involving team X"*) and global questions (*"main themes across all tickets"*). GraphRAG adds a knowledge graph layer with 3.4× accuracy improvement on these query types.

```
agentbreeder/rag/graph/
  extractor.py          # LLM entity + relationship extraction per chunk (Haiku)
  builder.py            # NetworkX graph + entity dedup (fuzzy + embedding similarity)
  community.py          # Leiden community detection (graspologic)
  summarizer.py         # LLM community summary generation
  lazy.py               # LazyGraphRAG: lightweight entity index, on-the-fly graph
  store/
    postgres.py         # Postgres-backed (default)
    neo4j.py            # Neo4j Aura (Enterprise option)
    base.py
  search/
    local.py            # entity mention detection → graph traversal → chunks
    global_search.py    # community summary similarity search → LLM synthesis
    hybrid.py           # naive vector + graph merged
    auto.py             # query classifier → routes to local/global/hybrid
  tool.py               # graph_search(query, mode) agent tool
```

**New deps (optional):** `graspologic`, `networkx`, `rapidfuzz`, `neo4j`  
Install as: `pip install agentbreeder[graphrag]`

**Two modes:**
- **Full GraphRAG** (Business+): entity extraction + community detection + summaries at index time → fast queries
- **LazyGraphRAG** (Teams+): entity-only index → builds mini-graph on-the-fly at query time → cheaper

---

### M-C3 · `agentbreeder.connectors.db` — Database Query Tool

**ROADMAP milestone:** v2.1  
**Cloud unblocks:** DB Connector Manager (Phase 2)  
**Cloud issue:** [#15](https://github.com/agentbreeder/agentbreeder-cloud/issues/15)

```
agentbreeder/connectors/db/
  __init__.py
  connector.py        # unified async connector (SQLAlchemy + adapters)
  adapters/
    postgres.py       # asyncpg
    mysql.py          # aiomysql
    bigquery.py       # google-cloud-bigquery
    snowflake.py      # snowflake-connector-python
    supabase.py       # supabase-py (Postgres under the hood)
  schema_browser.py   # list tables, columns, types for a connection
  query_builder.py    # natural-language → SQL via LLM + read-only validation
  tool.py             # db_query(sql) + db_schema() agent tools
```

**Safety:** All generated SQL validated as read-only (no INSERT/UPDATE/DELETE/DROP) before execution. Write mode requires explicit opt-in flag.

---

### M-C4 · `agentbreeder.eval.online` — Live Response Scoring

**ROADMAP milestone:** v2.3  
**Cloud unblocks:** Online Eval dashboard, score alerts (Phase 4)  
**Cloud issue:** [#16](https://github.com/agentbreeder/agentbreeder-cloud/issues/16)

```
agentbreeder/eval/
  online/
    __init__.py
    scorer.py         # LLM-as-judge scoring (Claude Haiku, async, non-blocking)
    metrics.py        # faithfulness, helpfulness, safety, latency_ok
    store.py          # write EvalScore to eval_results table
    alert.py          # rolling window check → emit alert if below threshold
```

**Scoring model:** Claude Haiku (fast + cheap). Runs after every agent response, non-blocking (Pub/Sub or background task). Score stored alongside the invocation trace.

---

### M-C5 · `agentbreeder.eval.offline` — Regression Test Runner

**ROADMAP milestone:** v2.3  
**Cloud unblocks:** Offline Eval suites, CI gate, GitHub App (Phase 4)  
**Cloud issue:** [#17](https://github.com/agentbreeder/agentbreeder-cloud/issues/17)

```
agentbreeder/eval/
  offline/
    __init__.py
    suite.py          # load/save golden dataset (JSON / CSV)
    runner.py         # parallel test execution (asyncio, configurable concurrency)
    metrics/
      exact_match.py
      semantic_sim.py # cosine distance between expected + actual embeddings
      llm_judge.py    # Claude Haiku rubric scoring (1–5)
      custom.py       # user-provided Python callable
    reporter.py       # aggregate results, regression vs baseline
    ci_gate.py        # exit non-zero if score drops > threshold
```

**CI integration:** `agentbreeder eval run --suite my-suite --agent my-agent --fail-under 0.90`

---

### M-C6 · `agentbreeder.guide` — Spec → Agent Generator

**ROADMAP milestone:** v2.4  
**Cloud unblocks:** Agent Guide UI (Phase 3)  
**Cloud issue:** [#18](https://github.com/agentbreeder/agentbreeder-cloud/issues/18)

The killer feature: paste a business requirement in plain English, get a production-ready agent config. No competitor has this.

```
agentbreeder/guide/
  __init__.py
  spec_parser.py      # extract intent, entities, constraints from NL spec
  generator.py        # Claude Sonnet prompt → full agent YAML config
  validator.py        # schema-validate generated config before returning
  test_generator.py   # generate 3-5 golden test cases from spec
  templates.py        # base templates generator builds on (per runtime)
  guardrails.py       # safety classifier, read-only SQL check, URL allowlist
```

**Generator model:** `claude-sonnet-4-6` with structured output (validated against agentbreeder YAML schema). Haiku for test case generation.

**Example input → output:**
```
Input:  "Customer support agent that looks up orders from Postgres,
         searches Zendesk KB, drafts responses, escalates if not confident"

Output (agentbreeder YAML):
  runtime: claude-sdk
  model: claude-haiku-4-5-20251001
  system_prompt: |
    You are a professional L1 customer support agent...
  tools:
    - type: db_query / connector: postgres-prod / ...
    - type: rag / source: zendesk-kb / ...
    - type: http / name: escalate_to_human / ...
  test_cases:
    - input: "Where is my order?" / expected_behavior: "Looks up order"
```

---

### M-C7 · `agentbreeder.serving` — Per-Agent REST Endpoint Server

**ROADMAP milestone:** v2.4  
**Cloud unblocks:** Chat API, chatbot widget (Phase 3)  
**Cloud issue:** [#19](https://github.com/agentbreeder/agentbreeder-cloud/issues/19)

```
agentbreeder/serving/
  __init__.py
  server.py           # FastAPI app factory per agent (mounts on Cloud Run)
  endpoints/
    chat.py           # POST /chat — streaming SSE + non-streaming JSON
    webhook.py        # POST /webhook — HMAC-verified external trigger
    batch.py          # POST /batch — async, callback URL, up to 1000 inputs
  session.py          # conversation thread management (message history)
  streaming.py        # SSE helper (delta chunks, tool call events, done)
  middleware.py       # API key validation, rate limiting, tenant injection
```

---

### M-C8 · `agentbreeder.sessions` — Session Checkpointing

**ROADMAP milestone:** v2.5  
**Cloud unblocks:** Sessions Dashboard, long-running agent support (Phase 3)  
**Cloud issues:** [#45](https://github.com/agentbreeder/agentbreeder-cloud/issues/45) [#48](https://github.com/agentbreeder/agentbreeder-cloud/issues/48)

Enables agents to run for hours, survive disconnections, and resume from mid-task state.

```
agentbreeder/sessions/
  __init__.py
  checkpoint.py       # serialize AgentState → GCS / Redis
  resume.py           # restore AgentState, re-enter at last checkpoint turn
  manager.py          # lifecycle: create, checkpoint, pause, resume, expire
  models.py           # AgentState, Checkpoint, SessionStatus dataclasses
  store/
    gcs.py            # GCS-backed (durable, long-lived)
    redis.py          # Redis-backed (fast, short-lived sessions)
```

**AgentState captures:** full message history, tool call results, scratchpad, pending tool queue, custom metadata.

---

### M-C9 · `agentbreeder.memory` — Long-Term Memory Bank

**ROADMAP milestone:** v2.5  
**Cloud unblocks:** Memory Browser UI (Phase 4)  
**Cloud issues:** [#46](https://github.com/agentbreeder/agentbreeder-cloud/issues/46) [#49](https://github.com/agentbreeder/agentbreeder-cloud/issues/49)

Agents remember facts, preferences, and events across separate sessions.

```
agentbreeder/memory/
  __init__.py
  store.py            # unified read/write interface
  backends/
    pgvector.py       # semantic memories (searchable by similarity)
    redis.py          # structured facts (fast key-value)
  types.py            # Fact | Preference | Event | Relationship
  extractor.py        # auto-extract memories from completed session (LLM)
  manager.py          # CRUD + TTL expiry + deduplication
  tool.py             # memory_recall(query, k) + memory_save(content, type)
```

---

### M-C10 · `agentbreeder.engine.spawner` — Dynamic Subagent Spawning

**ROADMAP milestone:** v2.5  
**Cloud unblocks:** Subagent execution graph in traces (Phase 4)  
**Cloud issue:** [#47](https://github.com/agentbreeder/agentbreeder-cloud/issues/47)

Orchestrator agents create specialist subagents at runtime — not pre-wired in a composer.

```
agentbreeder/engine/
  spawner.py          # spawn_agent() tool + ephemeral runtime management
```

**`spawn_agent()` signature:**
```python
async def spawn_agent(
    spec: str,                           # NL description of what subagent should do
    tools: list[str],                    # tool names to inherit
    model: str = "claude-haiku-...",     # cost-optimized default
    max_turns: int = 10,
    timeout_seconds: int = 60,
    inherit_rag: bool = False,
    inherit_tools: list[str] | None = None,
) -> AgentResult
```

**Safety:** max spawn depth 3, per-tenant rate limit, subagents cannot spawn beyond depth limit.

---

## Milestone Summary

| Milestone | Version | Modules | Cloud Phase Unblocked |
|---|---|---|---|
| M-C1 | v2.1 | `agentbreeder.rag` | Phase 2 (RAG Builder) |
| M-C3 | v2.1 | `agentbreeder.connectors.db` | Phase 2 (DB Connector) |
| M-C2 | v2.2 | `agentbreeder.rag.graph` | Phase 2 (GraphRAG toggle + Graph Explorer) |
| M-C4 | v2.3 | `agentbreeder.eval.online` | Phase 4 (Online Eval) |
| M-C5 | v2.3 | `agentbreeder.eval.offline` | Phase 4 (Offline Eval + CI gate) |
| M-C6 | v2.4 | `agentbreeder.guide` | Phase 3 (Agent Guide) |
| M-C7 | v2.4 | `agentbreeder.serving` | Phase 3 (Chat API + widget) |
| M-C8 | v2.5 | `agentbreeder.sessions` | Phase 3 (Sessions dashboard) |
| M-C9 | v2.5 | `agentbreeder.memory` | Phase 4 (Memory Browser) |
| M-C10 | v2.5 | `agentbreeder.engine.spawner` | Phase 4 (Subagent traces) |

---

## What Does NOT Move to OSS

These stay Cloud-only (proprietary):

| Capability | Why Cloud-only |
|---|---|
| Multi-tenant auth (JWT, SAML, SCIM) | SaaS infra, not developer tooling |
| Stripe billing + metering | Commercial layer |
| Org onboarding + Studio UI | Product surface |
| Cloud Run provisioner per tenant | Managed infra |
| SOC2 / HIPAA evidence pack | Enterprise compliance product |
| Cost dashboard + budget alerts | Commercial metering |
| MCP Marketplace | Ecosystem / revenue |
| Agent Guide UI | Cloud product surface (engine is OSS) |
| Graph Explorer UI | Cloud product surface (search is OSS) |
