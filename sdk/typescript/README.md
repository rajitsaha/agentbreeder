# @agentbreeder/sdk

[![npm](https://img.shields.io/npm/v/@agentbreeder/sdk)](https://www.npmjs.com/package/@agentbreeder/sdk)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![CI](https://github.com/rajitsaha/agentbreeder/actions/workflows/ci.yml/badge.svg)](https://github.com/rajitsaha/agentbreeder/actions)

TypeScript SDK for [AgentBreeder](https://agent-breeder.com) — Define Once. Deploy Anywhere. Govern Automatically.

---

## What is this?

`@agentbreeder/sdk` is the **Full Code tier** of AgentBreeder. You define agents programmatically in TypeScript using a fluent builder API; the SDK serializes your config to `agent.yaml` and hands it off to the AgentBreeder deploy pipeline — with RBAC, cost tracking, audit trail, and org-wide discoverability automatic.

The same deploy pipeline powers the No Code (UI drag-and-drop) and Low Code (handwritten YAML) tiers. All three compile to the same format. There is no SDK-only fast path that skips governance.

---

## Install

```bash
npm install @agentbreeder/sdk
```

Requires Node.js 18+. Ships as both ESM and CJS.

---

## Quick Start

```typescript
import { Agent, Tool, deploy } from "@agentbreeder/sdk";

const agent = new Agent("customer-support", {
  version: "1.0.0",
  team: "customer-success",
  owner: "alice@company.com",
  framework: "langgraph",
})
  .withModel("claude-sonnet-4", { fallback: "gpt-4o", temperature: 0.7 })
  .withPrompt("You are a helpful customer support agent.")
  .withTool(Tool.fromRef("tools/zendesk-mcp"))
  .withTool(Tool.fromRef("tools/order-lookup"))
  .withGuardrail("pii_detection")
  .withDeploy("aws", { region: "us-east-1" })
  .tag("support", "zendesk", "production");

// Validate before committing
const errors = agent.validate();
if (errors.length > 0) {
  console.error("Validation errors:", errors);
  process.exit(1);
}

// Write agent.yaml
import { writeFileSync } from "fs";
writeFileSync("agent.yaml", agent.toYaml());

// Or deploy directly
const result = await deploy(agent.toConfig(), "aws");
console.log("Live at:", result.endpoint);
```

---

## Multi-Agent Orchestration

The SDK provides four orchestration patterns via purpose-built classes. All patterns serialize to `orchestration.yaml` and share the same deploy pipeline.

### Pipeline — sequential chain

```typescript
import { Pipeline } from "@agentbreeder/sdk";

const pipeline = new Pipeline("triage-and-resolve", {
  version: "1.0.0",
  team: "customer-success",
})
  .step("triage", "agents/triage-agent")
  .step("resolver", "agents/resolver-agent")
  .step("summarizer", "agents/summary-agent")
  .withDeploy("aws");

writeFileSync("orchestration.yaml", pipeline.toYaml());
```

### FanOut — parallel workers with merge

```typescript
import { FanOut } from "@agentbreeder/sdk";

const fanout = new FanOut("multi-region-analysis", {
  version: "1.0.0",
  team: "data",
})
  .worker("us-analyst", "agents/regional-analyst")
  .worker("eu-analyst", "agents/regional-analyst")
  .worker("apac-analyst", "agents/regional-analyst")
  .merge("agents/report-merger")
  .withMergeStrategy("aggregate")
  .withDeploy("gcp");
```

### Supervisor — hierarchical delegation

```typescript
import { Supervisor } from "@agentbreeder/sdk";

const supervisor = new Supervisor("research-team", {
  version: "1.0.0",
  team: "research",
})
  .withSupervisorAgent("planner", "agents/research-planner")
  .worker("web-researcher", "agents/web-search-agent")
  .worker("doc-analyst", "agents/document-analyst")
  .worker("writer", "agents/report-writer")
  .withMaxIterations(5)
  .withDeploy("aws");
```

### Orchestration with routing

```typescript
import { Orchestration } from "@agentbreeder/sdk";

const router = new Orchestration("support-router", "router", {
  version: "1.0.0",
  team: "customer-success",
})
  .addAgent("billing", "agents/billing-agent")
  .addAgent("technical", "agents/technical-agent")
  .addAgent("returns", "agents/returns-agent")
  .withRoute("billing", "intent == 'billing'", "billing")
  .withRoute("technical", "intent == 'technical'", "technical")
  .withSharedState("redis", "redis://cache:6379")
  .withDeploy("aws");
```

---

## Key Classes

| Class / Function | Description |
|---|---|
| `Agent` | Fluent builder for a single agent. Produces `AgentConfig` / `agent.yaml`. |
| `Model` | Standalone model config builder with chained `.fallback()`, `.temperature()`, `.maxTokens()`, `.gateway()`. |
| `Tool` | Wraps a registry ref (`Tool.fromRef("tools/...")`) or an inline tool definition with `.withSchema()`. |
| `Pipeline` | Sequential orchestration — each step receives the previous step's output. |
| `FanOut` | Fan-out to parallel workers, merge results with a configurable `MergeStrategy`. |
| `Supervisor` | Hierarchical orchestration with a supervisor agent that delegates to workers. |
| `Orchestration` | Base class for custom routing, shared state, and any strategy not covered by the helpers. |
| `KeywordRouter` | Routes messages to agents by keyword match. |
| `IntentRouter` | Routes based on a pre-classified `context["intent"]` value. |
| `RoundRobinRouter` | Distributes messages across agents in round-robin order. |
| `deploy(config, target?)` | Async function that submits an `AgentConfig` to the AgentBreeder deploy pipeline. |
| `agentToYaml(config)` | Serialize a plain `AgentConfig` object to a YAML string. |
| `orchestrationToYaml(config)` | Serialize a plain `OrchestrationConfig` object to a YAML string. |

### `Agent` builder methods

| Method | Description |
|---|---|
| `.withModel(primary, opts?)` | Set primary model, optional `fallback`, `temperature`, `maxTokens`. |
| `.withPrompt(system)` | Set the system prompt (inline string or registry ref). |
| `.withTool(tool)` | Add a `Tool` instance. |
| `.withSubagent(ref, opts?)` | Reference another agent as a callable subagent. |
| `.withMcpServer(ref, transport?)` | Attach an MCP server (`stdio`, `sse`, or `streamable_http`). |
| `.withGuardrail(name)` | Add a guardrail by name (`pii_detection`, `content_filter`, `hallucination_check`, or a custom endpoint). |
| `.withDeploy(cloud, opts?)` | Set the deployment target and optional region, scaling, resources, env vars, secrets. |
| `.tag(...tags)` | Add discovery tags. |
| `.validate()` | Returns an array of validation error strings (empty = valid). |
| `.toYaml()` | Returns the `agent.yaml` content as a string. |
| `.toConfig()` | Returns the raw `AgentConfig` object. |

---

## Model builder

Use `Model` for reusable model configurations shared across agents:

```typescript
import { Model, Agent } from "@agentbreeder/sdk";

const model = new Model("claude-sonnet-4")
  .fallback("gpt-4o")
  .temperature(0.3)
  .maxTokens(8192)
  .gateway("litellm");

const agentA = new Agent("agent-a", { team: "eng" })
  .withModel(model.toConfig().primary, {
    fallback: model.toConfig().fallback,
    temperature: model.toConfig().temperature,
  });
```

---

## Tier Mobility

AgentBreeder supports moving between builder tiers at any time — no lock-in.

**Start in the SDK, view or share as YAML:**

```typescript
import { writeFileSync } from "fs";
writeFileSync("agent.yaml", agent.toYaml());
```

The exported YAML is fully human-readable and can be edited directly or committed to your repo as a Low Code artifact.

**Start from YAML, eject to SDK:**

```bash
agentbreeder eject agent.yaml --target typescript
```

This generates a TypeScript file that recreates the same agent using the SDK, which you can then extend programmatically.

**The invariant:** every tier compiles to the same `agent.yaml` schema. The deploy pipeline does not know or care which tier produced it.

---

## TypeScript types

All types are exported from the top-level package:

```typescript
import type {
  AgentConfig,
  CloudType,        // "aws" | "gcp" | "kubernetes" | "local"
  DeployConfig,
  FrameworkType,    // "langgraph" | "crewai" | "claude_sdk" | "openai_agents" | "google_adk" | "custom"
  McpServerRef,
  ModelConfig,
  OrchestrationConfig,
  PromptConfig,
  SubagentRef,
  ToolConfig,
  Visibility,       // "public" | "team" | "private"
} from "@agentbreeder/sdk";
```

---

## Links

- Documentation: [https://agent-breeder.com/docs](https://agent-breeder.com/docs)
- GitHub: [https://github.com/rajitsaha/agentbreeder](https://github.com/rajitsaha/agentbreeder)
- npm: [https://www.npmjs.com/package/@agentbreeder/sdk](https://www.npmjs.com/package/@agentbreeder/sdk)
- Python SDK: [`agentbreeder-sdk`](https://pypi.org/project/agentbreeder-sdk/) on PyPI
- Issues: [https://github.com/rajitsaha/agentbreeder/issues](https://github.com/rajitsaha/agentbreeder/issues)

---

## License

Apache 2.0 — see [LICENSE](../../LICENSE).
