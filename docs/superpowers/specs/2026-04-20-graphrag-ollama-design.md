# GraphRAG + Ollama + Website Animation Design

**Date:** 2026-04-20  
**Branch:** `feat-graphrag` worktree at `.worktrees/feat-graphrag/`

---

## Overview

Extend the existing `feat-graphrag` worktree to support local Ollama-based entity extraction, ship a working sample agent, animate the homepage hero, surface the knowledge graph in the dashboard UI, and lock everything in with Playwright tests.

---

## 1. Ollama Entity Extraction

**Current state:** `api/services/graph_extraction.py` has one extractor: `_call_claude()`, which calls `https://api.anthropic.com/v1/messages`. `DEFAULT_ENTITY_MODEL = "claude-haiku-4-5-20251001"`.

**Change:** Add `_call_ollama()` and route based on model name prefix — the same convention already used for embeddings (`ollama/nomic-embed-text`).

```
extract_entities(text, model="ollama/qwen2.5:7b")
  → model.startswith("ollama/") → _call_ollama(text, "qwen2.5:7b")
  → POST http://localhost:11434/api/chat
      { model: "qwen2.5:7b", format: "json", messages: [...] }
```

- New constant: `DEFAULT_OLLAMA_ENTITY_MODEL = "ollama/qwen2.5:7b"`
- Ollama uses `/api/chat` with `format: "json"` (structured output, works in qwen2.5:7b)
- Same JSON schema prompt as Claude: `{ entities: [...], relationships: [...] }`
- Fallback: empty result with warning log if Ollama is unreachable (same pattern as Claude's missing API key)
- `_call_claude` stays unchanged; no changes to GraphStore or graph_store.py

**Files changed:**
- `api/services/graph_extraction.py` — add `_call_ollama()`, update routing logic in `extract_entities()`
- `api/services/rag_service.py` — export `DEFAULT_OLLAMA_ENTITY_MODEL`

---

## 2. Sample Agent

**Location:** `examples/graphrag-ollama-agent/`

```
examples/graphrag-ollama-agent/
├── agent.yaml              # references kb/agentbreeder-docs
├── knowledge_base/         # source documents for ingestion
│   ├── architecture.md     # extracted from CLAUDE.md — deploy pipeline, principles
│   ├── agent-yaml.md       # agent.yaml specification from CLAUDE.md
│   └── cli-commands.md     # CLI command reference
├── ingest.py               # standalone ingestion script (no API server required)
└── README.md               # how to run: prerequisites, steps, expected output
```

**agent.yaml skeleton:**
```yaml
name: graphrag-demo-agent
version: "1.0.0"
team: examples
owner: demo@agentbreeder.dev
framework: claude_sdk
model:
  primary: ollama/qwen2.5:7b
knowledge_bases:
  - ref: kb/agentbreeder-docs
deploy:
  cloud: local
```

**ingest.py:** reads `knowledge_base/*.md` and POSTs each file to the RAG ingest HTTP API (`POST /api/v1/rag/indexes/{id}/ingest`) with `embedding_model=ollama/nomic-embed-text` and `entity_model=ollama/qwen2.5:7b`. Requires the local stack to be running (`docker compose up -d`). Prints extracted entity count and graph stats on completion.

**README.md covers:**
1. Prerequisites: Ollama installed, `ollama pull qwen2.5:7b`, `ollama pull nomic-embed-text`
2. Start local stack: `docker compose up -d`
3. Run ingest: `python examples/graphrag-ollama-agent/ingest.py`
4. Query the graph: `agentbreeder chat --agent graphrag-demo-agent "What are the GraphRAG concepts in AgentBreeder?"`
5. Expected output: graph stats (node count, edge count, entity types)

---

## 3. Homepage Animation

**Target file:** `website/src/components/hero.tsx`

**Approach:** Add an animated SVG knowledge graph layered behind the existing headline and CTA. Pure CSS animations — zero new dependencies. The graph shows 5 nodes representing AgentBreeder concepts: `agent.yaml`, `deploy`, `RBAC`, `cost`, `registry`. Edges animate with `stroke-dashoffset` traveling along the path. Nodes pulse with `scale` and `opacity`. The whole SVG sits as a background layer with `opacity-20` so it doesn't compete with the headline.

**Animation spec:**
- 5 nodes: `agent.yaml` (center), `deploy` (top-right), `RBAC` (bottom-right), `cost` (bottom-left), `registry` (top-left)
- 4 edges from `agent.yaml` to each outer node, animated with staggered 0.5s delays
- Node colors: green (`deploy`), purple (`RBAC`), blue (`cost`), amber (`registry`), white (`agent.yaml`)
- Keyframes: `node-pulse` (scale 1 → 1.2 → 1, 2s), `edge-travel` (stroke-dashoffset from 0 to full length, 3s linear infinite)
- Responsive: SVG uses `viewBox` and `width="100%"` — no fixed pixel sizes

**Integration:** render inside the existing `<div className="relative">` wrapper that holds the hero gradient orbs, layered with `absolute inset-0 z-0`.

---

## 4. Dashboard GraphRAG UI

**Target file:** `dashboard/src/pages/rag-builder.tsx`

**Approach:** Add a "Graph" tab to the existing tab bar in the RAG builder, visible only when `index.index_type === "graph" || === "hybrid"`. No new npm dependencies.

**Layout (Option C — split panel):**
```
┌─────────────────────────────────────────────────────┐
│ [Vector] [Graph] [Settings]                          │
├────────────────────┬────────────────────────────────┤
│  Entity List       │  Ego Graph                      │
│  ─────────────     │  ────────────                   │
│  Filter: [type ▼]  │  (click entity to center)       │
│                    │                                 │
│  • AgentBreeder    │    ◉ AgentBreeder               │
│    concept         │   /  \                          │
│  • deploy          │  ◉    ◉                         │
│    concept         │ RBAC  deploy                    │
│  • RBAC            │                                 │
│    concept         │  (SVG ego graph, 1-hop)         │
│  ...               │                                 │
│                    │                                 │
│  [< 1 / 4 >]       │                                 │
└────────────────────┴────────────────────────────────┘
```

**Data sources:**
- Entity list: `GET /api/v1/rag/indexes/{id}/entities?page=N&per_page=20&entity_type=X`
- Ego graph: `GET /api/v1/rag/indexes/{id}/relationships` (filtered to edges where subject or object is selected entity)
- Graph metadata: `GET /api/v1/rag/indexes/{id}/graph` (node_count, edge_count, entity_type_counts)

**SVG ego graph:** rendered inline in React — no external graph library. Draw selected node at center, 1-hop neighbors in a circle around it using trigonometry. Lines connecting them. Node labels truncated at 12 chars. Click a neighbor to re-center the graph on that node.

**New component:** `dashboard/src/components/GraphTab.tsx` — keeps `rag-builder.tsx` from getting larger.

---

## 5. Documentation Updates

**README.md** (root of `agentbreeder` repo): Add "GraphRAG" section after the existing "RAG" section. Covers: what it is, when to use graph vs vector, quick example (3 commands), link to full docs.

**website/src/content/docs/graphrag.mdx**: Already exists (from prior commit `f393f3e`). Update to include:
- Ollama entity extraction section (the `entity_model: ollama/qwen2.5:7b` config)
- Link to `examples/graphrag-ollama-agent/`
- Prerequisites callout (Ollama, qwen2.5:7b, nomic-embed-text)

---

## 6. Playwright E2E Tests

**File:** `dashboard/tests/07-graphrag.spec.ts` (new file)

**Test cases:**
1. **Create graph index** — POST via API fixture, verify `index_type: graph` shows "Graph" tab
2. **Entity list tab** — after ingest, entity list shows ≥ 1 entity with name and type badge
3. **Entity type filter** — filter dropdown changes visible entities
4. **Ego graph click** — clicking an entity renders the SVG ego graph panel
5. **Graph metadata** — node_count and edge_count badges show non-zero values

Tests use the mocked API fixtures from the existing `playwright.config.ts` setup — no live Ollama required for CI.

---

## 7. Merge Strategy

All work happens in the `feat-graphrag` worktree. After all tests pass:
1. `git add -u && git commit` in worktree
2. Merge to main: `git -C /Users/rajit/personal-github/agentbreeder merge feat-graphrag --no-ff`
3. Push main

---

## Implementation Order

1. `graph_extraction.py` — Ollama support (enables everything else)
2. `examples/graphrag-ollama-agent/` — sample agent + ingest script
3. `hero.tsx` — homepage animation
4. `GraphTab.tsx` + `rag-builder.tsx` — dashboard Graph tab
5. README + graphrag.mdx updates
6. `07-graphrag.spec.ts` — Playwright tests
7. Merge + push
