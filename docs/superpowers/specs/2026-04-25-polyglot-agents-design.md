# Polyglot Agent Runtime — Design Spec

**Date:** 2026-04-25  
**Status:** Approved  
**Author:** Rajit Saha  
**Scope:** Multi-language agent and MCP server support — TypeScript (Phase 1), Rust + Go (Phase 2), Kotlin (backlog)

---

## Problem Statement

AgentBreeder's deploy pipeline is language-agnostic at the container level but Python-only at the scaffold level. A team that builds agents in TypeScript, Rust, or Go must either maintain their own server wrapper (losing RAG, memory, A2A, tracing auto-wiring) or rewrite in Python. This blocks adoption for frontend-heavy teams (TypeScript), systems teams (Rust/Go), and organizations with language-standardization policies.

---

## Design Goals

1. **Full parity on day one** — a TypeScript agent gets RAG, memory, tools, A2A, and tracing automatically, same as a Python agent today.
2. **Zero Python for non-Python stacks** — a pure TypeScript or Rust stack contains no Python containers.
3. **Backward compatibility** — every existing `framework: langgraph` agent works unchanged.
4. **Minimal engine surface area** — adding a new language = one new file; adding a new framework = one new template class + one dict entry.
5. **Developer writes one file** — `agent.ts`, `main.rs`, or `main.go`. The platform owns the server.

---

## Design Decisions

### Decision 1: `runtime:` block with open `framework` string

**Chosen:** Introduce a `runtime:` block in `agent.yaml` with `language` (closed enum) and `framework` (open string validated against plugin registry, not JSON schema).

**Rejected alternatives:**
- Flat enum expansion (`framework: vercel-ai`) — conflates language and framework, enum hits 25+ values within a year, no structure.
- Separate `language` + `framework` top-level fields — creates invalid combos (`language: node, framework: langgraph`) requiring cross-field validation that is structurally equivalent to the `runtime:` block but worse-organized.

**Rationale:** Language changes the entire build system (base image, compiler, package manager). Framework changes only which server template is copied in. They belong at different levels of the hierarchy. `language` is a closed enum because there will never be 50 languages. `framework` is open because community frameworks should be addable without a platform PR.

### Decision 2: Sidecar owns all cross-cutting concerns

**Chosen:** All RAG retrieval, memory persistence, tool execution, A2A calls, tracing, and cost recording live in a sidecar container (AgentBreeder Platform Sidecar — APS). Language templates call the APS via a local HTTP API.

**Rejected alternative:** Per-template wiring (today's pattern, extended) — requires re-implementing RAG client, memory manager, tool bridge, A2A client in every language. Five languages × six concerns = 30 implementations to maintain.

**Rationale:** The sidecar IS the shared code. Promoting existing inline Python template logic to a sidecar service costs ~2 weeks of work but saves the equivalent of rewriting 25+ modules across 4 languages. It also makes each concern independently testable and versionable.

### Decision 3: Three sidecar implementations, not one

**Chosen:** Python APS (Phase 1, for Python agents), Node.js APS (Phase 1, for TypeScript agents), Go binary APS (Phase 2, for Rust/Go agents and long-term canonical implementation).

**Rejected alternative:** Single Python sidecar for all languages — forces Python into pure TypeScript/Rust/Go stacks, which is a blocker for teams with language-standardization policies.

**Rationale:** The APS exposes a well-defined HTTP API. Any implementation that satisfies the API spec is valid. The Go binary APS is a statically compiled binary (~15MB, no runtime dependency) and becomes the canonical implementation once Phase 2 ships.

### Decision 4: Plugin registry over hardcoded dispatch

**Chosen:** `LANGUAGE_REGISTRY: dict[str, LanguageRuntimeFamily]` — each family owns all framework templates for its language. `engine/builder.py` gains one function (`get_runtime()`) and zero other changes.

**Rejected alternative:** Extending the existing `if framework == "langgraph"` dispatch tree — already fragile at 6 entries, unmanageable at 20+.

### Decision 5: MCP servers use the same runtime + deploy pipeline

**Chosen:** `type: mcp-server` in config alongside `type: agent` (implicit default). Same `runtime:` block, same plugin registry, same `agentbreeder deploy` command.

**Rationale:** MCP servers are containers. The deploy pipeline doesn't care what's inside. Sharing the pipeline gives MCP servers governance, registry discovery, and RBAC for free.

---

## Architecture Overview

```
Developer writes:        agent.ts / main.rs / main.go   (their logic only)

agentbreeder deploy:
  1. Parse agent.yaml → RuntimeConfig
  2. RBAC check
  3. Resolve deps (KB refs → KB_INDEX_IDS, subagents → AGENT_TOOLS_JSON)
  4. get_runtime(config) → LanguageRuntimeFamily → FrameworkTemplate
     - copies server template into build context alongside developer's code
     - generates language-appropriate Dockerfile
  5. Build container image
  6. inject_sidecar(config) → appends APS container to deployment spec
  7. Provision + deploy (existing deployers unchanged)
  8. Register in registry

Running in production:
  ┌─────────────────────────────┐  ┌─────────────────────────┐
  │   Agent Container           │  │   APS Sidecar           │
  │                             │  │                         │
  │  server template (80 lines) │  │  RAG retrieval          │
  │  aps-client library         │◄─┤  Memory (Redis/PG)      │
  │  developer's agent.ts       │  │  Tool execution         │
  │                             │  │  A2A proxy              │
  │  GET  /health               │  │  OTel tracing           │
  │  POST /invoke               │  │  Cost recording         │
  │  POST /stream               │  │                         │
  └─────────────────────────────┘  └─────────────────────────┘
         same pod / task / compose network, port 9001
```

---

## Schema Changes

### `agent.yaml` — new `runtime:` block

```yaml
# Existing Python agents — unchanged, backward compatible
framework: langgraph

# New polyglot agents
runtime:
  language: node       # Enum: python | node | rust | go  (kotlin: backlog)
  framework: vercel-ai # Open string — validated against plugin registry
  version: "20"        # Language runtime version
  entrypoint: agent.ts # Optional. Defaults: agent.ts | agent.py | main.rs | main.go
```

`engine/config_parser.py` additions:
```python
class RuntimeConfig(BaseModel):
    language: Literal["python", "node", "rust", "go"]
    framework: str                    # open string
    version: str | None = None
    entrypoint: str | None = None

class AgentConfig(BaseModel):
    ...
    framework: FrameworkType | None = None   # legacy path, still valid
    runtime: RuntimeConfig | None = None     # new path, takes precedence
```

`engine/builder.py` addition (only change to existing file):
```python
def get_runtime(config: AgentConfig) -> RuntimeBuilder:
    if config.runtime:
        family = LANGUAGE_REGISTRY.get(config.runtime.language)
        if not family:
            raise UnsupportedLanguageError(config.runtime.language)
        return family()
    return PythonRuntimeFamily.from_framework(config.framework)
```

### `mcp-server.yaml` — new config type

```yaml
name: my-search-tools
version: 1.0.0
type: mcp-server
runtime:
  language: node
  framework: mcp-ts
  version: "20"
transport: http          # http | stdio
tools:
  - name: search_web
    description: "..."
    schema: { ... }
```

Schema file: `engine/schema/mcp-server.schema.json`

---

## AgentBreeder Platform Sidecar (APS)

### API Contract (all implementations must satisfy)

```
POST  /tools/execute      { name: str, input: dict }              → { output, duration_ms }
GET   /rag/search         ?query=&index_ids=&top_k=               → { chunks: [{text, score, source}] }
GET   /memory/load        ?thread_id=                             → { messages: [...] }
POST  /memory/save        { thread_id: str, messages: [...] }     → { ok }
POST  /a2a/call           { agent_name: str, input: any }         → { output }
POST  /trace/span         { name: str, attributes: dict }         → { span_id }
POST  /cost/record        { model: str, input_tokens, output_tokens } → { ok }
GET   /health                                                      → { status, version }
GET   /config                                                      → { agent_name, model, kb_index_ids, tools, memory_backend }
```

Auth: `Authorization: Bearer $APS_TOKEN` on every request. Token is a shared secret injected by the engine into both containers at deploy time.

### Sidecar Selection

| `runtime.language` | Sidecar image | Python in stack |
|---|---|---|
| `python` | `rajits/agentbreeder-aps-py` | Yes |
| `node` | `rajits/agentbreeder-aps-node` | No |
| `rust` / `go` | `rajits/agentbreeder-aps` (Go binary) | No |

### Injection into deployment specs

Every deployer calls `inject_sidecar(config, spec)` before submitting:
- **Docker Compose:** second service in the same network
- **Kubernetes:** second container in the same pod
- **ECS Fargate:** second container in the same task definition
- **Cloud Run:** second container in the same job (Cloud Run multi-container)

---

## Plugin Registry

```python
# engine/runtimes/registry.py
LANGUAGE_REGISTRY: dict[str, type[LanguageRuntimeFamily]] = {
    "python": PythonRuntimeFamily,
    "node":   NodeRuntimeFamily,
    "rust":   RustRuntimeFamily,
    "go":     GoRuntimeFamily,
}
```

### Supported frameworks per language

| Language | Frameworks (Phase 1) | Frameworks (Phase 2) |
|---|---|---|
| `python` | langgraph, crewai, claude_sdk, openai_agents, google_adk, custom | — |
| `node` | vercel-ai, mastra, langchain-js, openai-agents-ts, deepagent, custom | — |
| `rust` | — | rig, custom |
| `go` | — | langchaingo, custom |

Unknown framework → `CustomTemplate` for that language (warn, don't fail).

---

## Framework Templates

All templates: `GET /health`, `POST /invoke`, `POST /stream`.  
All templates use APS client for RAG, memory, tools, A2A, cost recording.  
Template size target: 80–120 lines per file.

### Developer's file (`agent.ts` / `main.rs` / `main.go`)

The developer writes only their agent logic. The platform template imports it:

```typescript
// agent.ts — complete developer file for a Vercel AI agent
import { openai } from '@ai-sdk/openai'
export const model = openai('gpt-4o')
export const systemPrompt = `You are a helpful assistant.`
export const tools = {}  // optional additional tools
```

```rust
// main.rs — complete developer file for a Rig agent
pub async fn run_agent(input: AgentInput) -> AgentOutput {
    let agent = rig::providers::openai::Client::from_env()
        .agent("gpt-4o")
        .preamble(&input.system)
        .build();
    let reply = agent.chat(&input.message, input.history).await?;
    AgentOutput { text: reply }
}
```

### APS client usage (identical across languages)

```typescript
// TypeScript
const [cfg, history, context, tools] = await Promise.all([
  aps.config(),
  aps.memory.load(thread_id),
  aps.rag.search(userMessage, { topK: 5 }),
  aps.tools.list(),
])
```

```rust
// Rust
let (cfg, history, context, tools) = tokio::join!(
    APS.config(),
    APS.memory_load(&thread_id),
    APS.rag_search(&user_msg, 5),
    APS.tools_list(),
);
```

```go
// Go
cfg,     _ := sidecar.Config(ctx)
history, _ := sidecar.Memory.Load(ctx, threadID)
context, _ := sidecar.RAG.Search(ctx, userMessage, 5)
tools,   _ := sidecar.Tools.List(ctx)
```

---

## MCP Server Templates

Templates per language: `mcp-ts`, `mcp-py`, `mcp-go`, `mcp-rust`.  
Developer writes only tool implementations. Template handles MCP protocol handshake, tool dispatch, transport (HTTP or stdio).

Developer file (`tools.ts`):
```typescript
export async function search_web({ query, max_results = 10 }) {
  return fetch(`https://api.search.com?q=${query}&n=${max_results}`).then(r => r.json())
}
```

Platform template wraps it into a fully compliant MCP server.

---

## A2A in Polyglot Context

Every agent template exposes `GET /.well-known/agent.json` (Agent Card) and accepts `POST /a2a/invoke`. Cross-language agent calls route through the APS:

```typescript
// TypeScript agent calling a Rust agent
const result = await aps.a2a.call('data-analysis-agent', { input: query })
```

The APS resolves agent names → endpoints via the platform registry. Language is transparent.

---

## File Inventory

### New files
```
engine/runtimes/registry.py
engine/runtimes/python.py              # reorganizes existing builders
engine/runtimes/node.py                # Phase 1
engine/runtimes/rust.py                # Phase 2
engine/runtimes/go.py                  # Phase 2
engine/runtimes/templates/python/      # existing templates moved here
engine/runtimes/templates/node/        # 6 TS templates + shared loader.ts
engine/runtimes/templates/rust/        # Phase 2
engine/runtimes/templates/go/          # Phase 2
engine/sidecar/python/                 # APS Python implementation
engine/sidecar/node/                   # APS Node.js implementation
engine/sidecar/go/                     # APS Go binary — Phase 2
engine/sidecar/client/ts/              # @agentbreeder/aps-client (npm)
engine/sidecar/client/rust/            # agentbreeder-aps (crates.io)
engine/sidecar/client/go/              # agentbreeder/aps-client (pkg.go.dev)
engine/schema/mcp-server.schema.json
website/content/docs/polyglot-agents.mdx
website/content/docs/mcp-authoring.mdx
```

### Changed files (minimal)
```
engine/builder.py          +15 lines  (get_runtime() function)
engine/config_parser.py    +25 lines  (RuntimeConfig model)
engine/schema/agent.schema.json       (runtime: block added)
engine/deployers/base.py   +20 lines  (inject_sidecar() helper)
cli/commands/init_cmd.py              (--language, --type flags)
```

---

## Phase Plan

### Phase 1 — TypeScript + Python+Node APS (~8 weeks)
- `runtime:` schema block + backward-compat `framework:` path
- Python APS (promote from template inline code)
- Node.js APS
- `NodeRuntimeFamily` + 5 TS templates
- `@agentbreeder/aps-client` npm package
- MCP scaffolding: `mcp-ts`, `mcp-py`
- `agentbreeder init --language node --framework vercel-ai`
- Website docs

### Phase 2 — Rust + Go + Go binary APS (~6 weeks)
- Go binary APS (statically compiled, replaces Python/Node APS for non-Python stacks)
- `RustRuntimeFamily` + `rig` + `custom-rust`
- `GoRuntimeFamily` + `langchaingo` + `custom-go`
- `agentbreeder-aps` Rust crate + Go module
- MCP scaffolding: `mcp-go`, `mcp-rust`
- `agentbreeder init --language rust`, `--language go`

### Backlog
- Kotlin/JVM (Koog, Spring AI, LangChain4j)
- Deno + Bun runtime variants
- Community framework registry (external PRs without platform change)
- Sidecar mesh for co-located orchestrations

---

## Testing Strategy

- Unit tests: each `LanguageRuntimeFamily.build()` returns a valid `ContainerImage` with correct Dockerfile
- Integration tests: `agentbreeder deploy --target local` for one TS agent and one Rust agent
- APS API contract tests: shared test suite run against all three APS implementations
- E2E: TypeScript agent calls Python agent via A2A, both backed by their respective sidecars

---

## Open Questions (resolved)

| Question | Decision |
|---|---|
| One sidecar or per-language? | Per-language (Python, Node, Go binary) |
| `framework` open or closed enum? | Open string, registry-validated |
| MCP servers in scope? | Yes — same pipeline, `type: mcp-server` |
| Go/Rust binary sidecar timeline? | Phase 2 (not backlog) |
| Kotlin timeline? | Backlog |
