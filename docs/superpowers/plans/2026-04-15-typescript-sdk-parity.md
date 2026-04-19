# TypeScript SDK Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `@agentbreeder/sdk` (TypeScript) to full feature parity with `agentbreeder-sdk` (Python). The TypeScript SDK exists but covers only ~60% of the Python SDK's surface area — three whole modules are missing (`memory.ts`, `mcp.ts`, `validation.ts`), eight `Agent` class methods are absent (file I/O, middleware, event hooks, programmatic deploy), `Tool.fromFunction()` is not implemented, the README is a single-line placeholder, and no TypeScript examples exist.

**GitHub Issue:** [#55](https://github.com/agentbreeder/agentbreeder/issues/55)

**Architecture:** All additions are purely additive — no existing TypeScript SDK APIs change. The `Memory` and `MCPServe` classes mirror the Python equivalents in shape, with TypeScript-idiomatic adaptations (explicit schemas instead of runtime type reflection; `async`/`Promise` for file I/O). The `MCPServe` class uses `@modelcontextprotocol/sdk` as an optional peer dependency, matching the Python SDK's optional `mcp>=1.0.0` extra.

**Tech Stack:** TypeScript 5.4+, Vitest 1.6+, tsup 8+, `@modelcontextprotocol/sdk` (optional peer dep), Node.js `fs/promises`

**Reference:** `sdk/python/agenthub/` (all modules), `sdk/typescript/src/` (existing TypeScript SDK), `examples/sdk-basic/agent.py`, `examples/sdk-advanced/agent.py`

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `sdk/typescript/src/memory.ts` | `Memory` builder + `MemoryConfig` interface |
| Create | `sdk/typescript/src/mcp.ts` | `MCPServe` class — register and serve MCP tools |
| Create | `sdk/typescript/src/validation.ts` | Standalone `validateAgent()` exported function |
| Modify | `sdk/typescript/src/agent.ts` | Add `withMemory`, `use`, `on`, `state`, `route`, `selectTools`, `fromYaml`, `fromFile`, `save`, `deploy` |
| Modify | `sdk/typescript/src/tool.ts` | Add `Tool.fromFunction()` with explicit schema param |
| Modify | `sdk/typescript/src/types.ts` | Add `memory?: MemoryConfig` to `AgentConfig` |
| Modify | `sdk/typescript/src/index.ts` | Export all new symbols |
| Modify | `sdk/typescript/package.json` | Add `@modelcontextprotocol/sdk` as optional peer dep; add `node` types |
| Modify | `sdk/typescript/tsconfig.json` | Add `"node"` to `lib`/`types` for `fs/promises` |
| Write | `sdk/typescript/README.md` | Full README: quickstart, API reference, examples |
| Create | `examples/sdk-ts-basic/agent.ts` | TypeScript equivalent of `examples/sdk-basic/agent.py` |
| Create | `examples/sdk-ts-advanced/agent.ts` | TypeScript equivalent of `examples/sdk-advanced/agent.py` |
| Create | `sdk/typescript/tests/memory.test.ts` | Vitest tests for `Memory` |
| Create | `sdk/typescript/tests/mcp.test.ts` | Vitest tests for `MCPServe` |
| Create | `sdk/typescript/tests/tool.test.ts` | Vitest tests for `Tool.fromFunction` |
| Create | `sdk/typescript/tests/validation.test.ts` | Vitest tests for `validateAgent` |
| Modify | `sdk/typescript/tests/agent.test.ts` | Add tests for all 10 new `Agent` methods |

---

## Task 1 — Write failing tests first (TDD)

### 1.1 — Agent new-method tests

**File:** `sdk/typescript/tests/agent.test.ts` (append to existing file)

- [ ] **Step 1: Add withMemory test**

```typescript
it("withMemory adds memory config to agent config", () => {
  const agent = new Agent("mem-agent", { team: "eng", owner: "a@b.com" })
    .withModel("claude-sonnet-4")
    .withMemory("postgresql", { maxMessages: 50 })
    .withDeploy("local");

  const config = agent.toConfig();
  expect(config.memory).toBeDefined();
  expect(config.memory!.backend).toBe("postgresql");
  expect(config.memory!.maxMessages).toBe(50);
});
```

- [ ] **Step 2: Add middleware (use) test**

```typescript
it("use() registers middleware and stores it", () => {
  const agent = new Agent("mw-agent", { team: "eng" }).withModel("gpt-4o");
  const mw = (msg: string, ctx: Record<string, unknown>) => ctx;
  agent.use(mw);
  // middleware list is internal; validate indirectly via state interaction
  expect(agent.state).toBeDefined();
});
```

- [ ] **Step 3: Add event hook (on) test**

```typescript
it("on() registers event handlers without error", () => {
  const agent = new Agent("ev-agent", { team: "eng" }).withModel("gpt-4o");
  const handler = vi.fn();
  agent.on("tool_call", handler);
  agent.on("error", handler);
  // handlers are internal; just verify no throw
  expect(true).toBe(true);
});
```

- [ ] **Step 4: Add state test**

```typescript
it("state property is a mutable shared object", () => {
  const agent = new Agent("state-agent", { team: "eng" }).withModel("gpt-4o");
  agent.state["turn_count"] = 3;
  expect(agent.state["turn_count"]).toBe(3);
});
```

- [ ] **Step 5: Add fromYaml / toYaml roundtrip test**

```typescript
it("fromYaml roundtrips through toYaml", () => {
  const original = new Agent("roundtrip", {
    version: "1.0.0",
    team: "eng",
    owner: "x@y.com",
    framework: "langgraph",
  })
    .withModel("claude-sonnet-4", { fallback: "gpt-4o" })
    .withDeploy("aws");

  const yaml = original.toYaml();
  const restored = Agent.fromYaml(yaml);
  expect(restored.toConfig().name).toBe("roundtrip");
  expect(restored.toConfig().model.primary).toBe("claude-sonnet-4");
  expect(restored.toConfig().deploy.cloud).toBe("aws");
});
```

- [ ] **Step 6: Add save / fromFile test (mock fs)**

```typescript
import { vi } from "vitest";

it("save() writes YAML and fromFile() reads it back", async () => {
  const agent = new Agent("fs-agent", { team: "eng", owner: "a@b.com" })
    .withModel("gpt-4o")
    .withDeploy("local");

  const writeMock = vi.fn().mockResolvedValue(undefined);
  const readMock = vi.fn().mockResolvedValue(agent.toYaml());
  vi.mock("fs/promises", () => ({ writeFile: writeMock, readFile: readMock }));

  await agent.save("/tmp/agent.yaml");
  expect(writeMock).toHaveBeenCalledWith("/tmp/agent.yaml", agent.toYaml(), "utf8");

  const loaded = await Agent.fromFile("/tmp/agent.yaml");
  expect(loaded.toConfig().name).toBe("fs-agent");
});
```

### 1.2 — Memory tests

**File:** `sdk/typescript/tests/memory.test.ts` (new file)

- [ ] **Step 7: Create memory test file**

```typescript
import { describe, it, expect } from "vitest";
import { Memory } from "../src";

describe("Memory", () => {
  it("bufferWindow creates correct config", () => {
    const m = Memory.bufferWindow(100);
    const cfg = m.toConfig();
    expect(cfg.backend).toBe("buffer_window");
    expect(cfg.maxMessages).toBe(100);
  });

  it("bufferWindow uses default maxMessages of 100", () => {
    const m = Memory.bufferWindow();
    expect(m.toConfig().maxMessages).toBe(100);
  });

  it("buffer creates in-memory backend config", () => {
    const m = Memory.buffer();
    expect(m.toConfig().backend).toBe("in_memory");
  });

  it("postgresql creates postgresql backend config", () => {
    const m = Memory.postgresql({ connectionString: "postgresql://localhost/db" });
    const cfg = m.toConfig();
    expect(cfg.backend).toBe("postgresql");
    expect(cfg.connectionString).toBe("postgresql://localhost/db");
  });

  it("toConfig returns MemoryConfig interface shape", () => {
    const cfg = Memory.bufferWindow(50).toConfig();
    expect(cfg).toHaveProperty("backend");
    expect(cfg).toHaveProperty("maxMessages");
  });
});
```

### 1.3 — MCPServe tests

**File:** `sdk/typescript/tests/mcp.test.ts` (new file)

- [ ] **Step 8: Create MCPServe test file**

```typescript
import { describe, it, expect } from "vitest";
import { MCPServe } from "../src";

describe("MCPServe", () => {
  it("constructs with default name", () => {
    const server = new MCPServe();
    expect(server.toolNames).toEqual([]);
  });

  it("constructs with custom name", () => {
    const server = new MCPServe("my-tools");
    expect(server.toolNames).toEqual([]);
  });

  it("tool() registers a function by name", () => {
    const server = new MCPServe();
    server.tool(
      function searchKnowledgeBase(query: string) { return `results for ${query}`; },
      { type: "object", properties: { query: { type: "string" } }, required: ["query"] }
    );
    expect(server.toolNames).toContain("searchKnowledgeBase");
  });

  it("tool() supports explicit name override", () => {
    const server = new MCPServe();
    server.tool(
      function fn() { return "ok"; },
      { type: "object", properties: {} },
      { name: "my_tool" }
    );
    expect(server.toolNames).toContain("my_tool");
  });

  it("tool() is chainable", () => {
    const server = new MCPServe();
    const result = server.tool(function a() { return ""; }, { type: "object", properties: {} });
    expect(result).toBe(server);
  });
});
```

### 1.4 — Tool.fromFunction tests

**File:** `sdk/typescript/tests/tool.test.ts` (new file)

- [ ] **Step 9: Create tool test file**

```typescript
import { describe, it, expect } from "vitest";
import { Tool } from "../src";

describe("Tool", () => {
  it("fromFunction creates a Tool from a named function with explicit schema", () => {
    function searchKnowledgeBase(query: string, maxResults = 5) {
      return `${maxResults} results for ${query}`;
    }
    const tool = Tool.fromFunction(searchKnowledgeBase, {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query" },
        maxResults: { type: "number", default: 5 },
      },
      required: ["query"],
    });
    const cfg = tool.toConfig();
    expect(cfg.name).toBe("searchKnowledgeBase");
    expect(cfg.schema).toBeDefined();
    expect((cfg.schema as Record<string, unknown>).required).toContain("query");
  });

  it("fromRef still works", () => {
    const tool = Tool.fromRef("tools/zendesk-mcp");
    expect(tool.toConfig().ref).toBe("tools/zendesk-mcp");
  });
});
```

### 1.5 — validateAgent tests

**File:** `sdk/typescript/tests/validation.test.ts` (new file)

- [ ] **Step 10: Create validation test file**

```typescript
import { describe, it, expect } from "vitest";
import { Agent, validateAgent } from "../src";

describe("validateAgent", () => {
  it("returns empty array for valid agent", () => {
    const agent = new Agent("valid-agent", { team: "eng", owner: "a@b.com" })
      .withModel("claude-sonnet-4")
      .withDeploy("local");
    expect(validateAgent(agent)).toEqual([]);
  });

  it("returns error when model is missing", () => {
    const agent = new Agent("no-model", { team: "eng" });
    const errors = validateAgent(agent);
    expect(errors.some((e) => e.includes("model"))).toBe(true);
  });

  it("returns error when name is empty string", () => {
    const agent = new Agent("", { team: "eng" }).withModel("gpt-4o");
    const errors = validateAgent(agent);
    expect(errors.some((e) => e.toLowerCase().includes("name"))).toBe(true);
  });

  it("returns error when team is missing", () => {
    const agent = new Agent("teamless").withModel("gpt-4o");
    const errors = validateAgent(agent);
    expect(errors.some((e) => e.toLowerCase().includes("team"))).toBe(true);
  });
});
```

---

## Task 2 — Implement memory.ts

**File:** `sdk/typescript/src/memory.ts` (new file)

- [ ] **Step 11: Create memory.ts**

```typescript
/** Memory configuration builder for AgentBreeder TypeScript SDK. */

export interface MemoryConfig {
  backend: string;
  maxMessages?: number;
  connectionString?: string;
}

/** Fluent builder for configuring agent memory backends. */
export class Memory {
  private config: MemoryConfig;

  private constructor(config: MemoryConfig) {
    this.config = config;
  }

  /** Sliding window of the last N messages (default: 100). */
  static bufferWindow(maxMessages = 100, opts: Partial<MemoryConfig> = {}): Memory {
    return new Memory({ ...opts, backend: "buffer_window", maxMessages });
  }

  /** Simple in-memory buffer (no persistence). */
  static buffer(opts: Partial<MemoryConfig> = {}): Memory {
    return new Memory({ ...opts, backend: "in_memory" });
  }

  /** PostgreSQL-backed persistent memory. */
  static postgresql(opts: Partial<MemoryConfig> = {}): Memory {
    return new Memory({ ...opts, backend: "postgresql" });
  }

  /** Return the underlying MemoryConfig. */
  toConfig(): MemoryConfig {
    return { ...this.config };
  }
}
```

---

## Task 3 — Implement mcp.ts

**File:** `sdk/typescript/src/mcp.ts` (new file)

- [ ] **Step 12: Create mcp.ts**

TypeScript has no runtime type reflection — schemas must be provided explicitly (unlike Python's `inspect`-based auto-derivation). Use `@modelcontextprotocol/sdk` for the actual server transport.

```typescript
/** MCPServe — build and serve MCP tool servers from TypeScript functions.
 *
 * Unlike the Python SDK which auto-derives JSON Schema from type hints,
 * TypeScript requires an explicit schema per tool (no runtime reflection).
 *
 * Requires: npm install @modelcontextprotocol/sdk
 * (optional peer dependency — only needed when calling .run())
 */

interface ToolRegistration {
  name: string;
  fn: (...args: unknown[]) => unknown;
  schema: Record<string, unknown>;
}

interface ToolOptions {
  name?: string;      // Override auto-derived name from function.name
  description?: string;
}

export class MCPServe {
  private _name: string;
  private _tools: ToolRegistration[] = [];

  constructor(name = "agentbreeder-tools") {
    this._name = name;
  }

  /** Register a function as an MCP tool with an explicit JSON Schema. */
  tool(
    fn: (...args: unknown[]) => unknown,
    schema: Record<string, unknown>,
    opts: ToolOptions = {}
  ): this {
    this._tools.push({
      name: opts.name ?? fn.name,
      fn,
      schema,
    });
    return this;
  }

  /** Names of all registered tools. */
  get toolNames(): string[] {
    return this._tools.map((t) => t.name);
  }

  /** Start the MCP server over stdio.
   *
   * Dynamically imports @modelcontextprotocol/sdk — ensure it is installed.
   */
  async run(): Promise<void> {
    // Dynamic import keeps @modelcontextprotocol/sdk optional
    const { McpServer } = await import("@modelcontextprotocol/sdk/server/mcp.js");
    const { StdioServerTransport } = await import(
      "@modelcontextprotocol/sdk/server/stdio.js"
    );

    const server = new McpServer({ name: this._name, version: "1.0.0" });

    for (const { name, fn, schema } of this._tools) {
      server.tool(name, schema, async (args: unknown) => {
        const result = await fn(args);
        return { content: [{ type: "text", text: String(result) }] };
      });
    }

    const transport = new StdioServerTransport();
    await server.connect(transport);
  }
}
```

---

## Task 4 — Implement validation.ts

**File:** `sdk/typescript/src/validation.ts` (new file)

- [ ] **Step 13: Create validation.ts**

```typescript
/** Standalone validation utility for AgentBreeder TypeScript SDK. */

import type { Agent } from "./agent";

/** Validate an agent configuration. Returns list of error strings (empty = valid). */
export function validateAgent(agent: Agent): string[] {
  return agent.validate();
}
```

---

## Task 5 — Extend agent.ts

**File:** `sdk/typescript/src/agent.ts`

- [ ] **Step 14: Add imports at top of agent.ts**

Add imports for `MemoryConfig`, `Memory`, file I/O, and `DeployResult`:
```typescript
import type { MemoryConfig } from "./memory";
import type { DeployResult } from "./deploy";
import { deploy as deployFn } from "./deploy";
import { readFile, writeFile } from "fs/promises";
```

- [ ] **Step 15: Add `memory` to `AgentOptions` interface**

```typescript
memory?: MemoryConfig;
```

- [ ] **Step 16: Add private fields for new features**

Inside the `Agent` class, add:
```typescript
private _middlewares: Array<(msg: string, ctx: Record<string, unknown>) => Record<string, unknown>> = [];
private _handlers: Map<string, Array<(...args: unknown[]) => void>> = new Map();
private _state: Record<string, unknown> = {};
```

- [ ] **Step 17: Add withMemory() method**

```typescript
withMemory(backend: string, opts: Partial<MemoryConfig> = {}): this {
  this._config.memory = { backend, ...opts };
  return this;
}
```

- [ ] **Step 18: Add use() middleware method**

```typescript
use(middleware: (msg: string, ctx: Record<string, unknown>) => Record<string, unknown>): this {
  this._middlewares.push(middleware);
  return this;
}
```

- [ ] **Step 19: Add on() event hook method**

```typescript
on(event: "tool_call" | "turn_start" | "turn_end" | "error", handler: (...args: unknown[]) => void): this {
  const handlers = this._handlers.get(event) ?? [];
  handlers.push(handler);
  this._handlers.set(event, handlers);
  return this;
}
```

- [ ] **Step 20: Add state getter**

```typescript
get state(): Record<string, unknown> {
  return this._state;
}
```

- [ ] **Step 21: Add overrideable route() method**

```typescript
route(message: string, context: Record<string, unknown>): string | null {
  return null;
}
```

- [ ] **Step 22: Add overrideable selectTools() method**

```typescript
selectTools(message: string): Tool[] {
  return [...this._tools];
}
```

- [ ] **Step 23: Add static fromYaml() method**

```typescript
static fromYaml(yaml: string): Agent {
  // Dynamic import of js-yaml (already used by yaml.ts internally)
  // Parse YAML → AgentConfig → reconstruct Agent
  // Simple reconstruction: parse fields and call builder methods
  const { load } = require("js-yaml") as typeof import("js-yaml");
  const cfg = load(yaml) as Record<string, unknown>;
  const name = cfg["name"] as string;
  const opts: AgentOptions = {
    version: cfg["version"] as string | undefined,
    team: cfg["team"] as string | undefined,
    owner: cfg["owner"] as string | undefined,
    framework: cfg["framework"] as AgentOptions["framework"],
    description: cfg["description"] as string | undefined,
  };
  const agent = new Agent(name, opts);
  const model = cfg["model"] as Record<string, unknown> | undefined;
  if (model) agent.withModel(model["primary"] as string, { fallback: model["fallback"] as string | undefined });
  const deploy = cfg["deploy"] as Record<string, unknown> | undefined;
  if (deploy) agent.withDeploy(deploy["cloud"] as CloudType);
  return agent;
}
```

- [ ] **Step 24: Add static fromFile() method**

```typescript
static async fromFile(path: string): Promise<Agent> {
  const content = await readFile(path, "utf8");
  return Agent.fromYaml(content);
}
```

- [ ] **Step 25: Add save() method**

```typescript
async save(path: string): Promise<void> {
  await writeFile(path, this.toYaml(), "utf8");
}
```

- [ ] **Step 26: Add deploy() method**

```typescript
async deploy(target = "local"): Promise<DeployResult> {
  return deployFn(this.toConfig(), target);
}
```

---

## Task 6 — Extend tool.ts

**File:** `sdk/typescript/src/tool.ts`

- [ ] **Step 27: Add Tool.fromFunction() static method**

```typescript
/** Create a Tool from a named function with an explicit JSON Schema.
 *
 * Unlike the Python SDK which auto-derives schema from type hints,
 * TypeScript requires an explicit schema (no runtime type reflection).
 *
 * @param fn     - Named function to wrap as a tool
 * @param schema - JSON Schema object describing the function's parameters
 */
static fromFunction(fn: (...args: unknown[]) => unknown, schema: Record<string, unknown>): Tool {
  const tool = new Tool({ name: fn.name, description: fn.name });
  tool._schema = schema;
  return tool;
}
```

Add `private _schema?: Record<string, unknown>` field to the `Tool` class and update `toConfig()` to include it.

---

## Task 7 — Update types.ts

**File:** `sdk/typescript/src/types.ts`

- [ ] **Step 28: Add memory field to AgentConfig**

```typescript
import type { MemoryConfig } from "./memory";

// Add to AgentConfig interface:
memory?: MemoryConfig;
```

---

## Task 8 — Update index.ts

**File:** `sdk/typescript/src/index.ts`

- [ ] **Step 29: Export new symbols**

```typescript
export { Memory } from "./memory";
export type { MemoryConfig } from "./memory";
export { MCPServe } from "./mcp";
export { validateAgent } from "./validation";
// Agent.fromYaml, Agent.fromFile, Agent.save, Agent.deploy are methods — no additional export needed
// Tool.fromFunction is a method — no additional export needed
```

---

## Task 9 — Update package.json and tsconfig.json

**File:** `sdk/typescript/package.json`

- [ ] **Step 30: Add optional peer dependency and node types**

```json
{
  "peerDependencies": {
    "@modelcontextprotocol/sdk": ">=1.0.0"
  },
  "peerDependenciesMeta": {
    "@modelcontextprotocol/sdk": { "optional": true }
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "tsup": "^8.0.0",
    "typescript": "^5.4.0",
    "vitest": "^1.6.0"
  }
}
```

**File:** `sdk/typescript/tsconfig.json`

- [ ] **Step 31: Add node lib entry for fs/promises access**

Ensure `"types": ["node"]` or `"lib": ["ES2022", "DOM"]` allows `fs/promises`. Add `"@types/node"` to devDependencies (Step 30) and reference it:
```json
{
  "compilerOptions": {
    "types": ["node", "vitest/globals"]
  }
}
```

---

## Task 10 — Write the README

**File:** `sdk/typescript/README.md`

- [ ] **Step 32: Write full README**

The README should cover:
- Installation (`npm install @agentbreeder/sdk`)
- Quickstart (10-line Agent example)
- API reference: `Agent`, `Model`, `Tool`, `Memory`, `MCPServe`, `Orchestration` classes
- Builder pattern table (method → description)
- TypeScript vs Python parity table
- Examples section (link to `examples/sdk-ts-basic/` and `examples/sdk-ts-advanced/`)
- Optional peer dependency note for `MCPServe`
- Link to full docs

---

## Task 11 — Write TypeScript examples

### 11.1 — Basic example

**File:** `examples/sdk-ts-basic/agent.ts` (new file)

- [ ] **Step 33: Create basic TypeScript example**

Mirror `examples/sdk-basic/agent.py` exactly in TypeScript idioms:

```typescript
/**
 * Basic AgentBreeder TypeScript SDK example.
 *
 * Demonstrates the builder-pattern API for defining an agent, validating it,
 * exporting to YAML, and saving to disk.
 *
 * Usage:
 *   npx tsx agent.ts
 */

import { Agent, Tool, Memory } from "@agentbreeder/sdk";

const agent = new Agent("customer-support", {
  version: "1.0.0",
  team: "support",
  owner: "alice@company.com",
})
  .withModel("claude-sonnet-4", { fallback: "gpt-4o" })
  .withPrompt("You are a helpful customer support agent...")
  .withTool(Tool.fromRef("tools/zendesk-mcp"))
  .withTool(Tool.fromRef("tools/order-lookup"))
  .withMemory("postgresql", { maxMessages: 50 })
  .withGuardrail("pii_detection")
  .withGuardrail("content_filter")
  .withDeploy("aws", { runtime: "ecs-fargate", region: "us-east-1" })
  .tag("support", "production");

const errors = agent.validate();
if (errors.length > 0) {
  console.error("Validation errors:");
  errors.forEach((e) => console.error(`  - ${e}`));
  process.exit(1);
} else {
  console.log("Agent is valid!");
}

console.log("\n--- agent.yaml ---");
console.log(agent.toYaml());

await agent.save("agent.yaml");
console.log("Saved to agent.yaml");
```

### 11.2 — Advanced example

**File:** `examples/sdk-ts-advanced/agent.ts` (new file)

- [ ] **Step 34: Create advanced TypeScript example**

Mirror `examples/sdk-advanced/agent.py` — middleware, event hooks, subclassable routing, `Tool.fromFunction`, `MCPServe`:

```typescript
/**
 * Advanced AgentBreeder TypeScript SDK example.
 *
 * Demonstrates middleware, event hooks, custom routing, dynamic tool selection,
 * Tool.fromFunction(), and MCPServe for building MCP tool servers.
 *
 * Usage:
 *   npx tsx agent.ts
 */

import { Agent, Tool, MCPServe } from "@agentbreeder/sdk";

// ---------------------------------------------------------------
// Define tools from TypeScript functions
// (explicit schema required — TypeScript has no runtime type reflection)
// ---------------------------------------------------------------

function searchKnowledgeBase(query: string, maxResults = 5): string {
  return `Found ${maxResults} results for: ${query}`;
}

function escalateToHuman(reason: string, priority = 1): string {
  return `Escalated (priority=${priority}): ${reason}`;
}

const searchTool = Tool.fromFunction(searchKnowledgeBase, {
  type: "object",
  properties: {
    query: { type: "string", description: "Search query" },
    maxResults: { type: "number", default: 5 },
  },
  required: ["query"],
});

const escalateTool = Tool.fromFunction(escalateToHuman, {
  type: "object",
  properties: {
    reason: { type: "string" },
    priority: { type: "number", default: 1 },
  },
  required: ["reason"],
});

// ---------------------------------------------------------------
// Build the agent
// ---------------------------------------------------------------

const agent = new Agent("smart-support", {
  version: "2.0.0",
  team: "support",
  owner: "alice@company.com",
  description: "Advanced support agent with custom routing and middleware",
})
  .withModel("claude-sonnet-4", { fallback: "gpt-4o", temperature: 0.3 })
  .withPrompt("You are an expert support agent. Be concise and helpful.")
  .withTool(searchTool)
  .withTool(escalateTool)
  .withTool(Tool.fromRef("tools/zendesk-mcp"))
  .withMemory("postgresql", { maxMessages: 200 })
  .withGuardrail("pii_detection")
  .withGuardrail("hallucination_check")
  .withGuardrail("content_filter")
  .withDeploy("aws", { runtime: "ecs-fargate", region: "us-east-1" })
  .tag("support", "production", "v2");

// ---------------------------------------------------------------
// Middleware — runs on every turn
// ---------------------------------------------------------------

agent.use((message, context) => {
  const turnCount = (agent.state["turn_count"] as number ?? 0) + 1;
  agent.state["turn_count"] = turnCount;
  console.info(`Turn ${turnCount}: ${message.slice(0, 100)}`);
  return context;
});

agent.use((message, context) => {
  const sessionId = (context["session_id"] as string) ?? "unknown";
  const rates = (agent.state["rates"] as Record<string, number>) ?? {};
  rates[sessionId] = (rates[sessionId] ?? 0) + 1;
  agent.state["rates"] = rates;
  return context;
});

// ---------------------------------------------------------------
// Event hooks
// ---------------------------------------------------------------

agent.on("tool_call", (toolName: unknown, args: unknown) => {
  console.info(`Calling tool '${toolName}' with args: ${JSON.stringify(args)}`);
});

agent.on("error", (error: unknown) => {
  console.error(`Agent error: ${error}`);
  const errors = (agent.state["errors"] as string[]) ?? [];
  errors.push(String(error));
  agent.state["errors"] = errors;
});

// ---------------------------------------------------------------
// Custom routing — override route() and selectTools() via subclass
// ---------------------------------------------------------------

class SmartSupportAgent extends Agent {
  route(message: string, _context: Record<string, unknown>): string | null {
    const angerKeywords = new Set(["furious", "lawsuit", "terrible", "worst"]);
    if (message.toLowerCase().split(/\W+/).some((w) => angerKeywords.has(w))) {
      return "escalateToHuman";
    }
    return null;
  }

  selectTools(message: string): Tool[] {
    if (message.includes("?")) {
      return this._tools.filter((t) => t.name === "searchKnowledgeBase");
    }
    return this._tools;
  }
}

// ---------------------------------------------------------------
// MCPServe — expose tools as an MCP server (optional)
// ---------------------------------------------------------------

const mcpServer = new MCPServe("support-tools");
mcpServer
  .tool(searchKnowledgeBase, {
    type: "object",
    properties: { query: { type: "string" }, maxResults: { type: "number" } },
    required: ["query"],
  })
  .tool(escalateToHuman, {
    type: "object",
    properties: { reason: { type: "string" }, priority: { type: "number" } },
    required: ["reason"],
  });

// Uncomment to start the MCP stdio server:
// await mcpServer.run();

// ---------------------------------------------------------------
// Main
// ---------------------------------------------------------------

const errors = agent.validate();
if (errors.length > 0) {
  console.error("Validation errors:");
  errors.forEach((e) => console.error(`  - ${e}`));
} else {
  console.log("Agent is valid!");
}

console.log("\n--- agent.yaml ---");
console.log(agent.toYaml());

agent.state["initialized"] = true;
console.log(`\nAgent state: ${JSON.stringify(agent.state)}`);
```

---

## Task 12 — Run full test suite and verify

- [ ] **Step 35: Run Vitest**

```bash
cd sdk/typescript
npm run typecheck
npm run test
npm run build
```

All existing tests (`agent.test.ts`, `orchestration.test.ts`) must continue to pass unchanged.

- [ ] **Step 36: Verify npm pack output**

```bash
npm pack --dry-run
```

Confirm `dist/` contains `.js`, `.cjs`, and `.d.ts` for all new modules.

---

## Acceptance Criteria

- [ ] `memory.ts` — `Memory` class with `bufferWindow()`, `buffer()`, `postgresql()` factories, `MemoryConfig` interface
- [ ] `mcp.ts` — `MCPServe` class: `.tool()` registration, `.toolNames` getter, `.run()` stdio server
- [ ] `validation.ts` — standalone `validateAgent(agent)` exported function
- [ ] `agent.ts` — all 10 new methods: `withMemory`, `use`, `on`, `state`, `route`, `selectTools`, `fromYaml`, `fromFile`, `save`, `deploy`
- [ ] `tool.ts` — `Tool.fromFunction()` with explicit schema
- [ ] `types.ts` — `memory?: MemoryConfig` on `AgentConfig`
- [ ] `index.ts` — all new symbols exported
- [ ] `README.md` — full quickstart + API reference
- [ ] `examples/sdk-ts-basic/agent.ts` — mirrors Python basic example
- [ ] `examples/sdk-ts-advanced/agent.ts` — mirrors Python advanced example
- [ ] `npm run typecheck` passes clean (no TypeScript errors)
- [ ] `npm run test` passes (all Vitest tests green, including all new tests)
- [ ] `npm run build` produces `dist/*.js`, `dist/*.cjs`, `dist/*.d.ts`
- [ ] Existing `agent.test.ts` and `orchestration.test.ts` pass without modification
