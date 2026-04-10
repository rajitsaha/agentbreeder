# Agent-Build Skill Design

**Date:** 2026-04-10
**Status:** Approved

## Summary

A Claude Code skill (`/agent-build`) that conversationally collects user preferences and scaffolds a complete, tier-interoperable AgentBreeder agent project. The output works across all three builder tiers: No Code (visual UI), Low Code (YAML), and Full Code (Python SDK).

## Approach

Hybrid: Claude asks questions conversationally, leverages existing template generators from `cli/commands/init_cmd.py`, and adds smart customization (tailored prompts, tool stubs, layout metadata, Docker config).

## Conversation Flow

Claude collects these inputs one at a time:

1. **Agent name** — slug-friendly, validated (`^[a-z0-9][a-z0-9-]*[a-z0-9]$`)
2. **Purpose/description** — free text describing what the agent does
3. **Framework** — langgraph | crewai | claude_sdk | openai_agents | google_adk | custom
4. **Cloud target** — local | aws | gcp | kubernetes
5. **Tools needed** — free text list; Claude generates tool stubs + MCP refs
6. **Team & owner** — defaults from git config, user confirms

## Generated Project Structure

```
<agent-name>/
├── agent.yaml              # Canonical config (Low Code)
├── agent.py                # Working agent code (Full Code)
├── requirements.txt        # Python deps (framework-specific)
├── Dockerfile              # Local testing + cloud deploy
├── docker-compose.yml      # docker compose up for local testing
├── .env.example            # API key template
├── .agentbreeder/
│   └── layout.json         # Visual builder layout (No Code)
├── tests/
│   └── test_agent.py       # Basic smoke test
└── README.md               # Quick start guide
```

## Tier Interoperability

- `agent.yaml` is the single source of truth across all tiers
- `.agentbreeder/layout.json` stores visual canvas metadata (node positions, edges, zoom). Never in `agent.yaml`
- `agent.py` is the Full Code entrypoint, compatible with `agentbreeder eject`
- The UI renders any project with `agent.yaml` + `.agentbreeder/layout.json`

## layout.json Schema

```json
{
  "version": "1.0",
  "canvas": { "zoom": 1.0, "x": 0, "y": 0 },
  "nodes": [
    { "id": "agent", "type": "agent", "position": { "x": 400, "y": 300 }, "data": { "ref": "agent.yaml" } },
    { "id": "model", "type": "model", "position": { "x": 400, "y": 100 }, "data": { "ref": "model.primary" } },
    { "id": "tool-N", "type": "tool", "position": { "x": ..., "y": ... }, "data": { "ref": "tools[N]" } }
  ],
  "edges": [
    { "id": "e-model-agent", "source": "model", "target": "agent" },
    { "id": "e-agent-tool-N", "source": "agent", "target": "tool-N" }
  ]
}
```

Tool nodes are arranged in a fan around the agent node (right side, evenly spaced). Model node sits above, prompt node to the left.

## Smart Generation (Beyond Templates)

- System prompt tailored to the stated purpose
- Tool stubs matching user-described tools (not generic `get_weather`)
- Framework-appropriate model defaults
- docker-compose with correct ports, health checks, env passthrough
- Smoke test that validates the agent loads and responds

## Output Location

Standalone directory — created wherever the user specifies or defaults to `./<agent-name>` relative to cwd.

## Skill Location

`.claude/commands/agent-build.md` — invoked via `/agent-build` in Claude Code.
