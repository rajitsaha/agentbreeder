# Phase 6: Claude SDK Advanced Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bump anthropic to >=0.50.0, add ClaudeSDKConfig with adaptive thinking / prompt caching / provider routing, and wire all config into server template startup.

**Architecture:** AgentConfig gains an optional `claude_sdk: ClaudeSDKConfig` sub-config. The runtime builder's `_build_env_block()` writes thinking/caching/routing config as Dockerfile ENV directives. The server template reads those env vars at startup to construct the right `AsyncAnthropic*` client variant and configure thinking/caching on every `messages.create()` call.

**Tech Stack:** anthropic>=0.50.0, AsyncAnthropic, AsyncAnthropicVertex, AsyncAnthropicBedrock, adaptive thinking, prompt caching

---

## Task 1: Add `ClaudeSDKConfig` to `engine/config_parser.py`, update JSON schema, bump requirements version

**Files changed:**
- `engine/config_parser.py`
- `engine/schema/agent.schema.json`
- `engine/runtimes/claude_sdk.py` (version bump only)

### Steps

- [ ] **1a. Add `ClaudeSDKThinkingConfig`, `ClaudeSDKRoutingConfig`, and `ClaudeSDKConfig` Pydantic models to `engine/config_parser.py`** — insert after `GuardrailConfig` (line 119) and before `AgentConfig` (line 122):

```python
class ClaudeSDKThinkingConfig(BaseModel):
    enabled: bool = False
    effort: str = "high"  # "high" | "medium" | "low"  (adaptive mode for Opus 4.6 / Sonnet 4.6)


class ClaudeSDKRoutingConfig(BaseModel):
    provider: str = "anthropic"  # "anthropic" | "vertex_ai" | "bedrock"
    project_id: str | None = None   # GCP project ID (required for vertex_ai)
    region: str | None = None       # Cloud region (required for vertex_ai / bedrock)


class ClaudeSDKConfig(BaseModel):
    thinking: ClaudeSDKThinkingConfig = Field(default_factory=ClaudeSDKThinkingConfig)
    prompt_caching: bool = False
    routing: ClaudeSDKRoutingConfig = Field(default_factory=ClaudeSDKRoutingConfig)
```

- [ ] **1b. Add `claude_sdk` optional field to `AgentConfig`** — add after the `access` field (line 141):

```python
claude_sdk: ClaudeSDKConfig = Field(default_factory=ClaudeSDKConfig)
```

- [ ] **1c. Add `claude_sdk` block to `engine/schema/agent.schema.json`** — add as a new top-level property inside `"properties"` (after the `"access"` block, before the closing `}`). Also add `"claude_sdk"` to `"additionalProperties": false` is already set so the new property must appear:

```json
"claude_sdk": {
  "type": "object",
  "description": "Claude SDK advanced configuration (only applies when framework: claude_sdk)",
  "additionalProperties": false,
  "properties": {
    "thinking": {
      "type": "object",
      "description": "Adaptive thinking configuration (Opus 4.6 / Sonnet 4.6)",
      "additionalProperties": false,
      "properties": {
        "enabled": {
          "type": "boolean",
          "default": false,
          "description": "Enable adaptive thinking"
        },
        "effort": {
          "type": "string",
          "enum": ["high", "medium", "low"],
          "default": "high",
          "description": "Thinking effort level (adaptive mode — do NOT use budget_tokens on Opus 4.6/Sonnet 4.6)"
        }
      }
    },
    "prompt_caching": {
      "type": "boolean",
      "default": false,
      "description": "Auto-inject cache_control on system prompts >= 2048 tokens (Sonnet 4.6) or >= 4096 tokens (Opus 4.6/Haiku 4.5) for 10x cost reduction on cache hits"
    },
    "routing": {
      "type": "object",
      "description": "Provider routing (Anthropic direct, Vertex AI, or AWS Bedrock)",
      "additionalProperties": false,
      "properties": {
        "provider": {
          "type": "string",
          "enum": ["anthropic", "vertex_ai", "bedrock"],
          "default": "anthropic",
          "description": "Which provider endpoint to route to"
        },
        "project_id": {
          "type": "string",
          "description": "GCP project ID (required for vertex_ai; supports ${ENV_VAR} interpolation)"
        },
        "region": {
          "type": "string",
          "description": "Cloud region (required for vertex_ai and bedrock)"
        }
      }
    }
  }
}
```

- [ ] **1d. Bump `anthropic` version constraint in `engine/runtimes/claude_sdk.py` `get_requirements()`** — change line 138 from `"anthropic>=0.40.0"` to `"anthropic>=0.50.0"`.

- [ ] **1e. Verify** — run the config parser unit tests and confirm JSON schema validation still passes for an agent.yaml without a `claude_sdk` block (it is optional):

```bash
cd /Users/rajit/personal-github/agentbreeder
pytest tests/unit/test_config_parser.py -v
```

- [ ] **1f. Commit:**

```bash
git add engine/config_parser.py engine/schema/agent.schema.json engine/runtimes/claude_sdk.py
git commit -m "feat(claude-sdk): add ClaudeSDKConfig Pydantic model, JSON schema block, bump anthropic>=0.50.0"
```

---

## Task 2: Extend `_build_env_block()` in `engine/runtimes/claude_sdk.py` with thinking/caching/routing ENV vars

**Files changed:**
- `engine/runtimes/claude_sdk.py`

### Context

The current `build()` method (lines 92–131) writes a Dockerfile with the static `DOCKERFILE_TEMPLATE` string. There is no `_build_env_block()` helper yet — this task adds it and integrates it into `build()`.

### Steps

- [ ] **2a. Add `_build_env_block()` method to `ClaudeSDKRuntime`** — insert between `get_entrypoint` (line 133) and `get_requirements` (line 136). The method reads `config.claude_sdk` and emits a multiline string of `ENV` directives suitable for insertion into the Dockerfile:

```python
def _build_env_block(self, config: AgentConfig) -> str:
    """Build Dockerfile ENV directives from AgentConfig.

    Writes:
    - Core agent identity (AGENT_NAME, AGENT_VERSION, AGENT_MODEL, AGENT_MAX_TOKENS)
    - deploy.env_vars (non-secret environment variables)
    - claude_sdk thinking config (AGENT_THINKING_ENABLED, AGENT_THINKING_EFFORT)
    - claude_sdk caching config (AGENT_PROMPT_CACHING)
    - claude_sdk routing config (AGENT_ROUTING_PROVIDER, AGENT_ROUTING_PROJECT_ID,
                                  AGENT_ROUTING_REGION)
    """
    lines: list[str] = []

    # Core agent identity
    lines.append(f"ENV AGENT_NAME={config.name}")
    lines.append(f"ENV AGENT_VERSION={config.version}")
    lines.append(f"ENV AGENT_MODEL={config.model.primary}")
    if config.model.max_tokens is not None:
        lines.append(f"ENV AGENT_MAX_TOKENS={config.model.max_tokens}")
    if config.model.temperature is not None:
        lines.append(f"ENV AGENT_TEMPERATURE={config.model.temperature}")

    # deploy.env_vars (non-secret, safe to bake into image layer)
    for key, value in config.deploy.env_vars.items():
        lines.append(f"ENV {key}={value}")

    # Claude SDK — thinking
    sdk = config.claude_sdk
    lines.append(f"ENV AGENT_THINKING_ENABLED={'true' if sdk.thinking.enabled else 'false'}")
    lines.append(f"ENV AGENT_THINKING_EFFORT={sdk.thinking.effort}")

    # Claude SDK — prompt caching
    lines.append(f"ENV AGENT_PROMPT_CACHING={'true' if sdk.prompt_caching else 'false'}")

    # Claude SDK — routing
    lines.append(f"ENV AGENT_ROUTING_PROVIDER={sdk.routing.provider}")
    if sdk.routing.project_id is not None:
        lines.append(f"ENV AGENT_ROUTING_PROJECT_ID={sdk.routing.project_id}")
    if sdk.routing.region is not None:
        lines.append(f"ENV AGENT_ROUTING_REGION={sdk.routing.region}")

    return "\n".join(lines)
```

- [ ] **2b. Update `DOCKERFILE_TEMPLATE` string to include a `{env_block}` placeholder** — replace the static template at the module level (lines 21–43) with:

```python
DOCKERFILE_TEMPLATE = """\
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY . .

# Non-root user for security
RUN useradd -m -r agent && chown -R agent:agent /app
USER agent

# Agent environment configuration
{env_block}

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \\
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
"""
```

- [ ] **2c. Update `build()` to format the template with the env block** — change lines 122–123 in `build()` from:

```python
dockerfile = build_dir / "Dockerfile"
dockerfile.write_text(DOCKERFILE_TEMPLATE)
```

to:

```python
env_block = self._build_env_block(config)
dockerfile_content = DOCKERFILE_TEMPLATE.format(env_block=env_block)
dockerfile = build_dir / "Dockerfile"
dockerfile.write_text(dockerfile_content)
```

Also update the `ContainerImage` construction to pass `dockerfile_content` instead of the raw template:

```python
return ContainerImage(
    tag=tag,
    dockerfile_content=dockerfile_content,
    context_dir=build_dir,
)
```

- [ ] **2d. Verify existing build tests still pass:**

```bash
cd /Users/rajit/personal-github/agentbreeder
pytest tests/unit/test_runtime_claude_sdk.py -v
```

- [ ] **2e. Commit:**

```bash
git add engine/runtimes/claude_sdk.py
git commit -m "feat(claude-sdk): add _build_env_block() writing thinking/caching/routing ENV vars into Dockerfile"
```

---

## Task 3: Add provider routing (Vertex AI / Bedrock / default) to `claude_sdk_server.py` startup

**Files changed:**
- `engine/runtimes/templates/claude_sdk_server.py`

### Context

The current server template (lines 74–83) loads the agent module at startup but never constructs an `AsyncAnthropic*` client directly — it relies on the user's `agent.py` to provide one. However, for the routing feature to work transparently (so users can point their agent at Vertex AI or Bedrock just via `agent.yaml` without changing their code), the server must intercept `isinstance(_agent, anthropic.AsyncAnthropic)` dispatch in `_run_agent` and replace it with the right client variant.

The approach: introduce a module-level `_client` variable constructed at startup from env vars. In `_run_agent`, when the loaded agent is an `AsyncAnthropic` instance OR when no client-type object was found (the agent is a callable/object), we use `_client` directly for `AsyncAnthropic`-path dispatch.

### Steps

- [ ] **3a. Add `_client` and `_thinking_config` module-level variables and a `_build_client()` helper** — insert before the `_load_agent` function (before line 52):

```python
# Module-level client and config — initialized at startup
_client: Any = None
_thinking_config: dict[str, Any] | None = None
_prompt_caching_enabled: bool = False
```

- [ ] **3b. Add `_build_client()` helper function** — insert after `_load_agent` (after line 71), before the `_agent = None` line:

```python
def _build_client() -> Any:
    """Construct the correct AsyncAnthropic* client based on AGENT_ROUTING_PROVIDER env var.

    Supported providers:
    - "anthropic" (default): AsyncAnthropic — uses ANTHROPIC_API_KEY
    - "vertex_ai": AsyncAnthropicVertex — uses GOOGLE_APPLICATION_CREDENTIALS + project/region
    - "bedrock": AsyncAnthropicBedrock — uses AWS credentials + region
    """
    import anthropic

    provider = os.getenv("AGENT_ROUTING_PROVIDER", "anthropic")

    if provider == "vertex_ai":
        project_id = os.getenv("AGENT_ROUTING_PROJECT_ID")
        region = os.getenv("AGENT_ROUTING_REGION", "us-east5")
        if not project_id:
            raise ValueError(
                "AGENT_ROUTING_PROVIDER=vertex_ai requires AGENT_ROUTING_PROJECT_ID to be set"
            )
        logger.info("Using Vertex AI provider (project=%s, region=%s)", project_id, region)
        return anthropic.AsyncAnthropicVertex(project_id=project_id, region=region)

    if provider == "bedrock":
        region = os.getenv("AGENT_ROUTING_REGION", "us-east-1")
        logger.info("Using AWS Bedrock provider (region=%s)", region)
        return anthropic.AsyncAnthropicBedrock(aws_region=region)

    # Default: Anthropic direct
    logger.info("Using Anthropic direct provider")
    return anthropic.AsyncAnthropic()
```

- [ ] **3c. Update `startup()` to initialize `_client`, `_thinking_config`, and `_prompt_caching_enabled`** — replace lines 78–83:

```python
@app.on_event("startup")
async def startup() -> None:
    global _agent, _client, _thinking_config, _prompt_caching_enabled  # noqa: PLW0603
    logger.info("Loading agent...")
    _agent = _load_agent()
    _client = _build_client()
    logger.info("Agent loaded successfully")

    # Adaptive thinking (Opus 4.6 / Sonnet 4.6 — uses type:adaptive, NOT budget_tokens)
    if os.getenv("AGENT_THINKING_ENABLED") == "true":
        effort = os.getenv("AGENT_THINKING_EFFORT", "high")
        _thinking_config = {"type": "adaptive"}
        logger.info("Adaptive thinking enabled (effort=%s)", effort)
        # Store effort on the config dict for use in output_config
        _thinking_config["_effort"] = effort

    _prompt_caching_enabled = os.getenv("AGENT_PROMPT_CACHING") == "true"
    if _prompt_caching_enabled:
        logger.info("Prompt caching enabled")
```

- [ ] **3d. Update `_run_agent()` to use `_client` for `AsyncAnthropic`-path dispatch** — replace the `isinstance(_agent, anthropic.AsyncAnthropic)` branch (lines 117–126) with a routing-aware dispatch. Now `_client` is always the right client type, so when the loaded agent IS an `AsyncAnthropic` instance (any variant), redirect through `_client` instead:

```python
# anthropic.AsyncAnthropic / AsyncAnthropicVertex / AsyncAnthropicBedrock client
# Use _client (routing-aware) instead of _agent directly, since _build_client()
# may have constructed a different variant (Vertex AI or Bedrock).
if isinstance(_agent, (anthropic.AsyncAnthropic,)):
    return await _call_client(_client, model, system_prompt, messages)
```

Add a new `_call_client()` helper (implementation in Task 4 — this step just stubs the import path). For now add a placeholder reference; Task 4 will provide the full body.

- [ ] **3e. Verify the server template is syntactically valid:**

```bash
cd /Users/rajit/personal-github/agentbreeder
python -c "import ast; ast.parse(open('engine/runtimes/templates/claude_sdk_server.py').read()); print('OK')"
```

- [ ] **3f. Commit:**

```bash
git add engine/runtimes/templates/claude_sdk_server.py
git commit -m "feat(claude-sdk): add provider routing startup — AsyncAnthropicVertex / AsyncAnthropicBedrock / default"
```

---

## Task 4: Add adaptive thinking + prompt caching auto-apply to `claude_sdk_server.py` `messages.create()` call

**Files changed:**
- `engine/runtimes/templates/claude_sdk_server.py`

### Context

`_run_agent()` currently hardcodes `max_tokens=1024` (the BUG-2 identified in GitHub Issue #45) and has no thinking or caching logic. This task:
1. Fixes BUG-2 by reading `AGENT_MAX_TOKENS` from env.
2. Extracts all `messages.create()` calls into a shared `_call_client()` helper so thinking/caching logic lives in one place.
3. Applies `thinking={"type": "adaptive"}` + `output_config={"effort": "..."}` when `_thinking_config` is set.
4. Auto-applies `cache_control` to system prompts that exceed the model-specific threshold.

### Caching thresholds (from Anthropic docs):
- `claude-sonnet-4-6`: >= 2048 tokens (approximated as >= 2048 chars for server-side estimate)
- `claude-opus-4` / `claude-haiku-4-5` and older: >= 4096 tokens

### Steps

- [ ] **4a. Add `_get_cache_threshold()` helper** — insert after `_build_client()`:

```python
def _get_cache_threshold(model: str) -> int:
    """Return the minimum system prompt character length for prompt caching eligibility.

    Anthropic caching requires system prompts to meet a minimum token count.
    We use character count as a cheap proxy (1 token ≈ 4 chars).
    - Sonnet 4.6: 2048 tokens → ~8192 chars
    - Opus 4.6 / Haiku 4.5 and others: 4096 tokens → ~16384 chars
    """
    if "sonnet" in model.lower():
        return 8192   # 2048 tokens * ~4 chars/token
    return 16384      # 4096 tokens * ~4 chars/token
```

- [ ] **4b. Add `_build_system_param()` helper** — insert after `_get_cache_threshold()`:

```python
def _build_system_param(system_prompt: str, model: str) -> str | list[dict[str, Any]]:
    """Build the system parameter for messages.create().

    If prompt caching is enabled and the system prompt is long enough,
    returns a content block list with cache_control injected.
    Otherwise returns the raw string (or empty string if no system prompt).
    """
    if not system_prompt:
        return ""

    if _prompt_caching_enabled and len(system_prompt) >= _get_cache_threshold(model):
        return [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    return system_prompt
```

- [ ] **4c. Add `_call_client()` helper** — this is the single location where `messages.create()` is called, applying BUG-2 fix, thinking, and caching:

```python
async def _call_client(
    client: Any,
    model: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
) -> str:
    """Call client.messages.create() with thinking and caching applied.

    - Fixes BUG-2: reads max_tokens from AGENT_MAX_TOKENS env var (default 4096).
    - Applies adaptive thinking when AGENT_THINKING_ENABLED=true.
    - Auto-applies prompt caching when AGENT_PROMPT_CACHING=true and system prompt
      meets the model-specific length threshold.
    """
    max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
    temperature_str = os.getenv("AGENT_TEMPERATURE")

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    # System prompt (may become a content block list if caching is applied)
    system = _build_system_param(system_prompt, model)
    if system:
        kwargs["system"] = system

    # Temperature (only set if not using thinking — Anthropic API rejects both)
    if temperature_str and not _thinking_config:
        kwargs["temperature"] = float(temperature_str)

    # Adaptive thinking (Opus 4.6 / Sonnet 4.6)
    # NOTE: budget_tokens is deprecated on these models — use type:adaptive + output_config
    if _thinking_config:
        thinking = {"type": _thinking_config["type"]}
        kwargs["thinking"] = thinking
        effort = _thinking_config.get("_effort", "high")
        kwargs["output_config"] = {"effort": effort}
        # Interleaved thinking requires the beta header for streaming;
        # for non-streaming we still set the beta flag so the API accepts thinking blocks.
        kwargs["betas"] = ["interleaved-thinking-2025-05-14"]

    response = await client.messages.create(**kwargs)
    return _extract_text(response)
```

- [ ] **4d. Update `_run_agent()` to use `_call_client()` for all direct-client dispatch paths** — replace the full body of `_run_agent()` (lines 108–153):

```python
async def _run_agent(input_data: str) -> str:
    """Run the agent, dispatching based on the type of object loaded from agent.py."""
    import anthropic

    model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    system_prompt = os.getenv("AGENT_SYSTEM_PROMPT", "")
    messages = [{"role": "user", "content": input_data}]

    # AsyncAnthropic / AsyncAnthropicVertex / AsyncAnthropicBedrock client
    # Always dispatch through _client (routing-aware) not _agent directly,
    # because _build_client() may have constructed a different variant.
    if isinstance(_agent, anthropic.AsyncAnthropic):
        return await _call_client(_client, model, system_prompt, messages)

    # anthropic.Anthropic (sync) client — run in thread to avoid blocking
    # Still uses _client for routing, but wrapped in asyncio.to_thread for sync compat.
    if isinstance(_agent, anthropic.Anthropic):
        # Sync path: build kwargs manually then run in thread
        max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
        sync_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        system = _build_system_param(system_prompt, model)
        if system:
            sync_kwargs["system"] = system
        response = await asyncio.to_thread(_agent.messages.create, **sync_kwargs)
        return _extract_text(response)

    # Async callable: async def agent(input: str) -> str
    if callable(_agent) and asyncio.iscoroutinefunction(_agent):
        return await _agent(input_data)

    # Object with async run() method
    if hasattr(_agent, "run") and asyncio.iscoroutinefunction(_agent.run):
        return await _agent.run(input_data)

    msg = (
        "Loaded agent object is not a supported type. "
        "Expected: anthropic.AsyncAnthropic, anthropic.Anthropic, "
        "async callable, or object with async run() method."
    )
    raise TypeError(msg)
```

- [ ] **4e. Verify syntax:**

```bash
cd /Users/rajit/personal-github/agentbreeder
python -c "import ast; ast.parse(open('engine/runtimes/templates/claude_sdk_server.py').read()); print('OK')"
```

- [ ] **4f. Commit:**

```bash
git add engine/runtimes/templates/claude_sdk_server.py
git commit -m "feat(claude-sdk): adaptive thinking, prompt caching auto-apply, fix max_tokens hardcode (BUG-2)"
```

---

## Task 5: Integration tests for routing, thinking, and caching

**Files changed:**
- `tests/unit/test_claude_sdk_advanced.py` (new file)

### Scope

These are unit tests (no live Anthropic API calls). All SDK client constructors and `messages.create()` are mocked. Tests cover:
1. `ClaudeSDKConfig` parsing (Pydantic model + JSON schema)
2. `_build_env_block()` output for all three routing providers
3. `_build_client()` constructs the right client type based on env vars
4. `_call_client()` applies thinking and caching correctly
5. Prompt caching threshold logic
6. `get_requirements()` version constraint is `>=0.50.0`

### Steps

- [ ] **5a. Create `tests/unit/test_claude_sdk_advanced.py`:**

```python
"""Tests for Phase 6 Claude SDK advanced features:
adaptive thinking, prompt caching, provider routing, and version bump.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.config_parser import (
    AgentConfig,
    ClaudeSDKConfig,
    ClaudeSDKRoutingConfig,
    ClaudeSDKThinkingConfig,
    FrameworkType,
)
from engine.runtimes.claude_sdk import ClaudeSDKRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides: object) -> AgentConfig:
    defaults: dict[str, object] = {
        "name": "test-agent",
        "version": "1.0.0",
        "team": "test",
        "owner": "test@example.com",
        "framework": FrameworkType.claude_sdk,
        "model": {"primary": "claude-sonnet-4-6"},
        "deploy": {"cloud": "local"},
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)


def _make_config_with_sdk(**sdk_kwargs: object) -> AgentConfig:
    """Build an AgentConfig with a claude_sdk block."""
    return _make_config(claude_sdk=ClaudeSDKConfig(**sdk_kwargs))


# ---------------------------------------------------------------------------
# Task 1: ClaudeSDKConfig Pydantic model
# ---------------------------------------------------------------------------

class TestClaudeSDKConfig:
    def test_defaults(self) -> None:
        cfg = ClaudeSDKConfig()
        assert cfg.thinking.enabled is False
        assert cfg.thinking.effort == "high"
        assert cfg.prompt_caching is False
        assert cfg.routing.provider == "anthropic"
        assert cfg.routing.project_id is None
        assert cfg.routing.region is None

    def test_thinking_enabled(self) -> None:
        cfg = ClaudeSDKConfig(thinking=ClaudeSDKThinkingConfig(enabled=True, effort="medium"))
        assert cfg.thinking.enabled is True
        assert cfg.thinking.effort == "medium"

    def test_routing_vertex_ai(self) -> None:
        cfg = ClaudeSDKConfig(
            routing=ClaudeSDKRoutingConfig(
                provider="vertex_ai",
                project_id="my-gcp-project",
                region="us-east5",
            )
        )
        assert cfg.routing.provider == "vertex_ai"
        assert cfg.routing.project_id == "my-gcp-project"
        assert cfg.routing.region == "us-east5"

    def test_routing_bedrock(self) -> None:
        cfg = ClaudeSDKConfig(
            routing=ClaudeSDKRoutingConfig(provider="bedrock", region="us-west-2")
        )
        assert cfg.routing.provider == "bedrock"
        assert cfg.routing.region == "us-west-2"

    def test_prompt_caching_flag(self) -> None:
        cfg = ClaudeSDKConfig(prompt_caching=True)
        assert cfg.prompt_caching is True

    def test_agent_config_accepts_claude_sdk_block(self) -> None:
        config = _make_config_with_sdk(
            thinking={"enabled": True, "effort": "high"},
            prompt_caching=True,
            routing={"provider": "vertex_ai", "project_id": "proj", "region": "us-east5"},
        )
        assert config.claude_sdk.thinking.enabled is True
        assert config.claude_sdk.prompt_caching is True
        assert config.claude_sdk.routing.provider == "vertex_ai"

    def test_agent_config_claude_sdk_defaults_when_omitted(self) -> None:
        config = _make_config()
        assert config.claude_sdk.thinking.enabled is False
        assert config.claude_sdk.prompt_caching is False
        assert config.claude_sdk.routing.provider == "anthropic"


# ---------------------------------------------------------------------------
# Task 2: _build_env_block()
# ---------------------------------------------------------------------------

class TestBuildEnvBlock:
    def test_default_routing_vars(self) -> None:
        runtime = ClaudeSDKRuntime()
        config = _make_config()
        block = runtime._build_env_block(config)
        assert "ENV AGENT_ROUTING_PROVIDER=anthropic" in block

    def test_thinking_disabled_by_default(self) -> None:
        runtime = ClaudeSDKRuntime()
        config = _make_config()
        block = runtime._build_env_block(config)
        assert "ENV AGENT_THINKING_ENABLED=false" in block

    def test_thinking_enabled_writes_correct_vars(self) -> None:
        runtime = ClaudeSDKRuntime()
        config = _make_config_with_sdk(
            thinking=ClaudeSDKThinkingConfig(enabled=True, effort="medium")
        )
        block = runtime._build_env_block(config)
        assert "ENV AGENT_THINKING_ENABLED=true" in block
        assert "ENV AGENT_THINKING_EFFORT=medium" in block

    def test_prompt_caching_enabled_writes_true(self) -> None:
        runtime = ClaudeSDKRuntime()
        config = _make_config_with_sdk(prompt_caching=True)
        block = runtime._build_env_block(config)
        assert "ENV AGENT_PROMPT_CACHING=true" in block

    def test_prompt_caching_disabled_writes_false(self) -> None:
        runtime = ClaudeSDKRuntime()
        config = _make_config()
        block = runtime._build_env_block(config)
        assert "ENV AGENT_PROMPT_CACHING=false" in block

    def test_vertex_ai_routing_writes_project_and_region(self) -> None:
        runtime = ClaudeSDKRuntime()
        config = _make_config_with_sdk(
            routing=ClaudeSDKRoutingConfig(
                provider="vertex_ai", project_id="my-project", region="us-east5"
            )
        )
        block = runtime._build_env_block(config)
        assert "ENV AGENT_ROUTING_PROVIDER=vertex_ai" in block
        assert "ENV AGENT_ROUTING_PROJECT_ID=my-project" in block
        assert "ENV AGENT_ROUTING_REGION=us-east5" in block

    def test_bedrock_routing_writes_region(self) -> None:
        runtime = ClaudeSDKRuntime()
        config = _make_config_with_sdk(
            routing=ClaudeSDKRoutingConfig(provider="bedrock", region="us-west-2")
        )
        block = runtime._build_env_block(config)
        assert "ENV AGENT_ROUTING_PROVIDER=bedrock" in block
        assert "ENV AGENT_ROUTING_REGION=us-west-2" in block

    def test_deploy_env_vars_written(self) -> None:
        runtime = ClaudeSDKRuntime()
        config = _make_config(deploy={"cloud": "local", "env_vars": {"LOG_LEVEL": "debug"}})
        block = runtime._build_env_block(config)
        assert "ENV LOG_LEVEL=debug" in block

    def test_model_max_tokens_written(self) -> None:
        runtime = ClaudeSDKRuntime()
        config = _make_config(model={"primary": "claude-sonnet-4-6", "max_tokens": 8192})
        block = runtime._build_env_block(config)
        assert "ENV AGENT_MAX_TOKENS=8192" in block

    def test_dockerfile_contains_env_block(self, tmp_path: Path) -> None:
        runtime = ClaudeSDKRuntime()
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("agent = None")
        (agent_dir / "requirements.txt").write_text("anthropic>=0.50.0")
        config = _make_config_with_sdk(prompt_caching=True)
        image = runtime.build(agent_dir, config)
        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "AGENT_PROMPT_CACHING=true" in dockerfile


# ---------------------------------------------------------------------------
# Task 3: Provider routing (_build_client)
# ---------------------------------------------------------------------------

class TestBuildClient:
    """Test _build_client() via env vars (imports server template at runtime to avoid
    FastAPI startup side effects — we test the helper function directly)."""

    def _import_build_client(self) -> Any:
        """Import _build_client from the server template module."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "claude_sdk_server",
            Path("engine/runtimes/templates/claude_sdk_server.py"),
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod._build_client

    @patch.dict(os.environ, {"AGENT_ROUTING_PROVIDER": "anthropic"}, clear=False)
    def test_default_returns_async_anthropic(self) -> None:
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_client = self._import_build_client()
            client = build_client()
            mock_cls.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "AGENT_ROUTING_PROVIDER": "vertex_ai",
            "AGENT_ROUTING_PROJECT_ID": "my-project",
            "AGENT_ROUTING_REGION": "us-east5",
        },
        clear=False,
    )
    def test_vertex_ai_returns_async_anthropic_vertex(self) -> None:
        with patch("anthropic.AsyncAnthropicVertex") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_client = self._import_build_client()
            client = build_client()
            mock_cls.assert_called_once_with(project_id="my-project", region="us-east5")

    @patch.dict(
        os.environ,
        {"AGENT_ROUTING_PROVIDER": "vertex_ai"},
        clear=False,
    )
    def test_vertex_ai_without_project_id_raises(self) -> None:
        # Remove PROJECT_ID if present
        env = {k: v for k, v in os.environ.items() if k != "AGENT_ROUTING_PROJECT_ID"}
        env["AGENT_ROUTING_PROVIDER"] = "vertex_ai"
        with patch.dict(os.environ, env, clear=True):
            build_client = self._import_build_client()
            with pytest.raises(ValueError, match="AGENT_ROUTING_PROJECT_ID"):
                build_client()

    @patch.dict(
        os.environ,
        {"AGENT_ROUTING_PROVIDER": "bedrock", "AGENT_ROUTING_REGION": "us-west-2"},
        clear=False,
    )
    def test_bedrock_returns_async_anthropic_bedrock(self) -> None:
        with patch("anthropic.AsyncAnthropicBedrock") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_client = self._import_build_client()
            client = build_client()
            mock_cls.assert_called_once_with(aws_region="us-west-2")


# ---------------------------------------------------------------------------
# Task 4: _call_client — thinking, caching, max_tokens fix
# ---------------------------------------------------------------------------

class TestCallClient:
    """Test _call_client() with mocked Anthropic client."""

    def _import_server_module(self) -> Any:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "claude_sdk_server_adv",
            Path("engine/runtimes/templates/claude_sdk_server.py"),
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"AGENT_MAX_TOKENS": "2048"}, clear=False)
    async def test_max_tokens_from_env(self) -> None:
        mod = self._import_server_module()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="hello")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mod._prompt_caching_enabled = False
        mod._thinking_config = None

        result = await mod._call_client(mock_client, "claude-sonnet-4-6", "", [{"role": "user", "content": "hi"}])

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 2048
        assert result == "hello"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {}, clear=False)
    async def test_default_max_tokens_is_4096(self) -> None:
        mod = self._import_server_module()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="hi")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mod._prompt_caching_enabled = False
        mod._thinking_config = None
        # Ensure no AGENT_MAX_TOKENS in env
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENT_MAX_TOKENS", None)
            await mod._call_client(mock_client, "claude-sonnet-4-6", "", [])
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 4096

    @pytest.mark.asyncio
    async def test_thinking_config_applied(self) -> None:
        mod = self._import_server_module()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="thought")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mod._prompt_caching_enabled = False
        mod._thinking_config = {"type": "adaptive", "_effort": "high"}

        await mod._call_client(mock_client, "claude-sonnet-4-6", "", [{"role": "user", "content": "think"}])

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["thinking"] == {"type": "adaptive"}
        assert call_kwargs["output_config"] == {"effort": "high"}
        assert "interleaved-thinking-2025-05-14" in call_kwargs["betas"]
        # temperature must NOT be set when thinking is active
        assert "temperature" not in call_kwargs

    @pytest.mark.asyncio
    async def test_prompt_caching_applied_for_long_system_prompt(self) -> None:
        mod = self._import_server_module()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="cached")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mod._prompt_caching_enabled = True
        mod._thinking_config = None

        long_system = "x" * 9000  # > 8192 chars threshold for sonnet

        await mod._call_client(
            mock_client, "claude-sonnet-4-6", long_system, [{"role": "user", "content": "hi"}]
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        system_param = call_kwargs["system"]
        assert isinstance(system_param, list)
        assert system_param[0]["type"] == "text"
        assert system_param[0]["cache_control"] == {"type": "ephemeral"}

    @pytest.mark.asyncio
    async def test_prompt_caching_not_applied_for_short_system_prompt(self) -> None:
        mod = self._import_server_module()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="short")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mod._prompt_caching_enabled = True
        mod._thinking_config = None

        short_system = "You are helpful."

        await mod._call_client(
            mock_client, "claude-sonnet-4-6", short_system, [{"role": "user", "content": "hi"}]
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        system_param = call_kwargs["system"]
        # Short prompt: should be a plain string, not a content block list
        assert isinstance(system_param, str)

    @pytest.mark.asyncio
    async def test_prompt_caching_not_applied_when_disabled(self) -> None:
        mod = self._import_server_module()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="no cache")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mod._prompt_caching_enabled = False
        mod._thinking_config = None

        long_system = "x" * 9000

        await mod._call_client(
            mock_client, "claude-sonnet-4-6", long_system, [{"role": "user", "content": "hi"}]
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert isinstance(call_kwargs["system"], str)


# ---------------------------------------------------------------------------
# Cache threshold logic
# ---------------------------------------------------------------------------

class TestCacheThreshold:
    def _get_threshold(self, model: str) -> int:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "claude_sdk_server_thresh",
            Path("engine/runtimes/templates/claude_sdk_server.py"),
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod._get_cache_threshold(model)

    def test_sonnet_threshold_is_lower(self) -> None:
        assert self._get_threshold("claude-sonnet-4-6") == 8192

    def test_opus_threshold_is_higher(self) -> None:
        assert self._get_threshold("claude-opus-4") == 16384

    def test_haiku_threshold_is_higher(self) -> None:
        assert self._get_threshold("claude-haiku-4-5") == 16384


# ---------------------------------------------------------------------------
# Requirements version
# ---------------------------------------------------------------------------

class TestRequirementsVersion:
    def test_anthropic_version_is_050_or_higher(self) -> None:
        runtime = ClaudeSDKRuntime()
        config = _make_config()
        reqs = runtime.get_requirements(config)
        anthropic_req = next((r for r in reqs if r.startswith("anthropic")), None)
        assert anthropic_req is not None
        # Must be >= 0.50.0, not the old >= 0.40.0
        assert "0.50.0" in anthropic_req or "0.50" in anthropic_req
        assert "0.40" not in anthropic_req
```

- [ ] **5b. Run all new tests and confirm they pass:**

```bash
cd /Users/rajit/personal-github/agentbreeder
pytest tests/unit/test_claude_sdk_advanced.py -v
```

- [ ] **5c. Run the full unit test suite to confirm no regressions:**

```bash
cd /Users/rajit/personal-github/agentbreeder
pytest tests/unit/ -v --tb=short
```

- [ ] **5d. Run coverage check:**

```bash
cd /Users/rajit/personal-github/agentbreeder
pytest tests/unit/test_claude_sdk_advanced.py tests/unit/test_runtime_claude_sdk.py \
    --cov=engine/runtimes/claude_sdk --cov=engine/config_parser \
    --cov-report=term-missing
```

- [ ] **5e. Commit:**

```bash
git add tests/unit/test_claude_sdk_advanced.py
git commit -m "test(claude-sdk): add unit tests for adaptive thinking, prompt caching, provider routing, version bump"
```

---

## Summary of all changed files

| File | Change |
|------|--------|
| `engine/config_parser.py` | Add `ClaudeSDKThinkingConfig`, `ClaudeSDKRoutingConfig`, `ClaudeSDKConfig` models; add `claude_sdk` field to `AgentConfig` |
| `engine/schema/agent.schema.json` | Add `claude_sdk` top-level schema block with `thinking`, `prompt_caching`, `routing` sub-objects |
| `engine/runtimes/claude_sdk.py` | Bump `anthropic>=0.40.0` → `>=0.50.0`; add `_build_env_block()`; update `DOCKERFILE_TEMPLATE` with `{env_block}` placeholder; update `build()` to format the template |
| `engine/runtimes/templates/claude_sdk_server.py` | Add `_client`, `_thinking_config`, `_prompt_caching_enabled` module globals; add `_build_client()`, `_get_cache_threshold()`, `_build_system_param()`, `_call_client()` helpers; update `startup()` to init all globals; update `_run_agent()` to use `_call_client()` |
| `tests/unit/test_claude_sdk_advanced.py` | New file — 30+ unit tests covering all phase 6 features |

## Key implementation constraints

- Do NOT use `budget_tokens` on Opus 4.6 or Sonnet 4.6 — it is deprecated. Use `thinking={"type": "adaptive"}` + `output_config={"effort": "high"|"medium"|"low"}` only.
- `budget_tokens` is still valid for older models (claude-3-5-sonnet etc.) but Phase 6 targets 0.50+ with the new adaptive API only.
- Adaptive thinking and `temperature` are mutually exclusive — never set both in the same `messages.create()` call.
- Prompt caching requires `betas` to be passed with the `cache-2024-11-22` header only for explicit cache writes in tool use; for system prompt caching via `cache_control` in content blocks, no extra beta header is needed.
- The `interleaved-thinking-2025-05-14` beta header is required when using `thinking` in streaming mode, and is safe (no-op ignored) in non-streaming mode — so it is always set when thinking is active.
- `AGENT_ROUTING_PROJECT_ID` should support `${ENV_VAR}` interpolation in `agent.yaml` (the deploy pipeline already resolves env var references before writing ENV directives, so this is handled upstream — the server template receives the resolved value).
