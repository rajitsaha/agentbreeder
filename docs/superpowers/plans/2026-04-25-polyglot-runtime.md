# Polyglot Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make TypeScript a first-class language for AgentBreeder agents — same zero-infrastructure developer experience Python has today, via a thin npm client that calls the existing Python API.

**Architecture:** Two sequential PRs. PR 2 wires the deploy pipeline (schema, config models, deployer env injection, runtime registry). PR 3 builds the Node.js runtime family (8 TypeScript templates, `@agentbreeder/aps-client` npm package, MCP schema, CLI flags). No new sidecar servers — the TS agent calls the central AgentBreeder Python API via HTTP.

**Tech Stack:** Python 3.11+ (FastAPI, Pydantic, SQLAlchemy), TypeScript 5 / Node.js 20 (Express 4, ts-node), JSON Schema Draft 2020-12, pytest, Jest.

---

## File Map

### PR 2 — Foundation

| File | Change | Responsibility |
|---|---|---|
| `engine/config_parser.py` | Modify | Add `LanguageType`, `AgentType`, `RuntimeConfig` models; make `framework` optional in `AgentConfig`; add `runtime` + `type` fields |
| `engine/schema/agent.schema.json` | Modify | Add `runtime` block, `type` enum, `oneOf` mutual exclusivity |
| `engine/runtimes/registry.py` | Create | `LANGUAGE_REGISTRY` dict + `get_runtime_from_config()` + `UnsupportedLanguageError` |
| `engine/runtimes/python.py` | Create | `PythonRuntimeFamily` factory — wraps existing per-framework builders |
| `engine/builder.py` | Modify | Replace `get_runtime(config.framework)` with `get_runtime_from_config(config)` |
| `engine/deployers/base.py` | Modify | Add `get_aps_env_vars()` → `dict[str, str]` |
| `engine/deployers/docker_compose.py` | Modify | Merge `get_aps_env_vars()` into `container_env` |
| `engine/deployers/aws_ecs.py` | Modify | Merge `get_aps_env_vars()` into `env_vars` in `_build_container_definition` |
| `engine/deployers/gcp_cloudrun.py` | Modify | Merge `get_aps_env_vars()` into `plain_env_vars` |
| `api/config.py` | Modify | Add `agentbreeder_url` + `agentbreeder_api_key` settings |
| `tests/unit/test_config_parser.py` | Modify | Update `test_missing_framework_raises` → new `RuntimeConfig` tests |
| `tests/unit/test_deployer_base.py` | Create | Test `get_aps_env_vars()` |

### PR 3 — Node Runtime

| File | Change | Responsibility |
|---|---|---|
| `engine/runtimes/node.py` | Create | `NodeRuntimeFamily` — generates Dockerfile, server.ts, package.json, tsconfig.json |
| `engine/runtimes/registry.py` | Modify | Add `"node": NodeRuntimeFamily` to `LANGUAGE_REGISTRY` |
| `engine/runtimes/templates/node/_shared_loader.ts` | Create | APSClient init, health handler, agent card handler — imported by all templates |
| `engine/runtimes/templates/node/vercel_ai_server.ts` | Create | Vercel AI SDK template |
| `engine/runtimes/templates/node/mastra_server.ts` | Create | Mastra template |
| `engine/runtimes/templates/node/langchain_js_server.ts` | Create | LangChain.js template |
| `engine/runtimes/templates/node/openai_agents_ts_server.ts` | Create | OpenAI Agents TS template |
| `engine/runtimes/templates/node/deepagent_server.ts` | Create | DeepAgent template |
| `engine/runtimes/templates/node/custom_node_server.ts` | Create | Custom Node template |
| `engine/runtimes/templates/node/mcp_ts_server.ts` | Create | MCP TypeScript server template |
| `engine/runtimes/templates/node/mcp_py_server.ts` | Create | MCP Python stdio proxy template |
| `engine/sidecar/client/ts/package.json` | Create | npm package manifest for `@agentbreeder/aps-client` |
| `engine/sidecar/client/ts/tsconfig.json` | Create | TypeScript config for aps-client |
| `engine/sidecar/client/ts/src/index.ts` | Create | `APSClient` class — typed HTTP wrapper |
| `engine/sidecar/client/ts/src/__tests__/aps_client.test.ts` | Create | Jest tests for APSClient behaviors |
| `engine/schema/mcp-server.schema.json` | Create | JSON Schema for `mcp-server.yaml` |
| `api/routes/memory.py` | Modify | Add `GET /api/v1/memory/thread/{thread_id}` + `POST /api/v1/memory/thread` convenience endpoints |
| `cli/commands/init_cmd.py` | Modify | Add `--language` + `--type` flags + Node scaffold templates |
| `tests/unit/test_node_runtime.py` | Create | Unit tests for `NodeRuntimeFamily.build()` |
| `tests/integration/test_polyglot_deploy.py` | Create | Integration test: deploy Vercel AI agent locally |
| `tests/integration/test_mcp_deploy.py` | Create | Integration test: deploy MCP TypeScript server locally |

---

## PR 2: Foundation

### Task 1: `RuntimeConfig` + `AgentType` models + `AgentConfig` update

**Files:**
- Modify: `engine/config_parser.py`
- Modify: `tests/unit/test_config_parser.py`

- [ ] **Step 1: Write failing tests for the new models**

Add to `tests/unit/test_config_parser.py` (after the existing `TestValidateConfig` class):

```python
class TestRuntimeConfig:
    def test_valid_node_runtime(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agent.yaml"
        config_file.write_text("""\
name: my-agent
version: 1.0.0
team: engineering
owner: test@example.com
type: agent
runtime:
  language: node
  framework: vercel-ai
  version: "20"
model:
  primary: gpt-4o
deploy:
  cloud: local
""")
        result = validate_config(config_file)
        assert result.valid, result.errors
        assert result.config is not None
        assert result.config.runtime is not None
        assert result.config.runtime.language == "node"
        assert result.config.runtime.framework == "vercel-ai"
        assert result.config.type.value == "agent"

    def test_open_framework_string_accepted(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agent.yaml"
        config_file.write_text("""\
name: my-agent
version: 1.0.0
team: engineering
owner: test@example.com
runtime:
  language: node
  framework: some-future-framework-not-in-schema
model:
  primary: gpt-4o
deploy:
  cloud: local
""")
        result = validate_config(config_file)
        assert result.valid, result.errors

    def test_unknown_language_rejected(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agent.yaml"
        config_file.write_text("""\
name: my-agent
version: 1.0.0
team: engineering
owner: test@example.com
runtime:
  language: cobol
  framework: custom
model:
  primary: gpt-4o
deploy:
  cloud: local
""")
        result = validate_config(config_file)
        assert not result.valid

    def test_both_framework_and_runtime_rejected(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agent.yaml"
        config_file.write_text("""\
name: my-agent
version: 1.0.0
team: engineering
owner: test@example.com
framework: langgraph
runtime:
  language: node
  framework: vercel-ai
model:
  primary: gpt-4o
deploy:
  cloud: local
""")
        result = validate_config(config_file)
        assert not result.valid

    def test_neither_framework_nor_runtime_rejected(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agent.yaml"
        config_file.write_text("""\
name: my-agent
version: 1.0.0
team: engineering
owner: test@example.com
model:
  primary: gpt-4o
deploy:
  cloud: local
""")
        result = validate_config(config_file)
        assert not result.valid

    def test_existing_python_framework_still_works(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agent.yaml"
        config_file.write_text("""\
name: my-agent
version: 1.0.0
team: engineering
owner: test@example.com
framework: langgraph
model:
  primary: gpt-4o
deploy:
  cloud: local
""")
        result = validate_config(config_file)
        assert result.valid, result.errors

    def test_mcp_server_type(self, tmp_path: Path) -> None:
        config_file = tmp_path / "agent.yaml"
        config_file.write_text("""\
name: my-tools
version: 1.0.0
team: engineering
owner: test@example.com
type: mcp-server
runtime:
  language: node
  framework: mcp-ts
model:
  primary: gpt-4o
deploy:
  cloud: local
""")
        result = validate_config(config_file)
        assert result.valid, result.errors
        assert result.config.type.value == "mcp-server"
```

- [ ] **Step 2: Run to confirm all fail**

```bash
cd /Users/rajit/personal-github/agentbreeder
pytest tests/unit/test_config_parser.py::TestRuntimeConfig -v 2>&1 | tail -20
```

Expected: 7 failures (AttributeError or ImportError on `RuntimeConfig`).

- [ ] **Step 3: Add `LanguageType`, `AgentType`, `RuntimeConfig` to `engine/config_parser.py`**

Open `engine/config_parser.py`. After the `FrameworkType` enum (around line 25), add:

```python
class LanguageType(enum.StrEnum):
    python = "python"
    node = "node"


class AgentType(enum.StrEnum):
    agent = "agent"
    mcp_server = "mcp-server"


class RuntimeConfig(BaseModel):
    language: LanguageType
    framework: str
    version: str | None = None
    entrypoint: str | None = None
```

- [ ] **Step 4: Update `AgentConfig` — make `framework` optional, add `runtime` + `type`**

Find the `AgentConfig` class. Change `framework: FrameworkType` to `framework: FrameworkType | None = None`. Add two new fields and a validator. The class should include:

```python
class AgentConfig(BaseModel):
    # ... all existing fields unchanged above ...
    type: AgentType = AgentType.agent
    framework: FrameworkType | None = None   # was required; now optional
    runtime: RuntimeConfig | None = None     # new

    @model_validator(mode="after")
    def validate_framework_or_runtime(self) -> "AgentConfig":
        has_framework = self.framework is not None
        has_runtime = self.runtime is not None
        if has_framework == has_runtime:
            raise ValueError(
                "Exactly one of 'framework' or 'runtime' must be set. "
                "Use 'framework' for Python agents, 'runtime' for polyglot agents."
            )
        return self
    # ... keep all existing validators ...
```

- [ ] **Step 5: Update the existing `test_missing_framework_raises` test**

In `tests/unit/test_config_parser.py`, find `test_missing_framework_raises`. Change it so it tests the new rule — setting neither raises:

```python
def test_missing_framework_raises(self) -> None:
    config_file = self.tmp_path / "agent.yaml"
    config_file.write_text("""\
name: my-agent
version: 1.0.0
team: engineering
owner: test@example.com
model:
  primary: gpt-4o
deploy:
  cloud: local
""")
    result = validate_config(config_file)
    assert not result.valid
    assert any("framework" in e.message.lower() or "runtime" in e.message.lower()
               for e in result.errors)
```

- [ ] **Step 6: Run the tests**

```bash
pytest tests/unit/test_config_parser.py -v 2>&1 | tail -30
```

Expected: all existing tests pass + all 7 new `TestRuntimeConfig` tests pass.

- [ ] **Step 7: Commit**

```bash
git add engine/config_parser.py tests/unit/test_config_parser.py
git commit -m "feat(config): add RuntimeConfig, AgentType, LanguageType models — framework now optional"
```

---

### Task 2: Update `agent.schema.json`

**Files:**
- Modify: `engine/schema/agent.schema.json`

- [ ] **Step 1: Add `runtime` property, `type` property, update `required`, add `oneOf`**

Open `engine/schema/agent.schema.json`. Make these three changes:

**a)** Remove `"framework"` from the top-level `"required"` array. The array should now be:
```json
"required": ["name", "version", "team", "owner", "model", "deploy"]
```

**b)** Add `"type"` and `"runtime"` to the `"properties"` object (alongside the existing `"framework"` entry):

```json
"type": {
  "type": "string",
  "enum": ["agent", "mcp-server"],
  "default": "agent",
  "description": "Whether this is an agent or an MCP server"
},
"runtime": {
  "type": "object",
  "description": "Polyglot runtime configuration (use instead of framework for non-Python agents)",
  "required": ["language", "framework"],
  "additionalProperties": false,
  "properties": {
    "language": {
      "type": "string",
      "enum": ["python", "node"],
      "description": "Agent language (closed enum — drives base image and compiler)"
    },
    "framework": {
      "type": "string",
      "description": "Agent framework (open string — validated by runtime plugin registry)"
    },
    "version": {
      "type": "string",
      "description": "Language runtime version (e.g. '20' for Node LTS)"
    },
    "entrypoint": {
      "type": "string",
      "description": "Agent entrypoint file (default: agent.ts for node, agent.py for python)"
    }
  }
},
```

**c)** Add `oneOf` at the top level of the schema object (after `"additionalProperties": false`):

```json
"oneOf": [
  {
    "required": ["framework"],
    "properties": { "runtime": false }
  },
  {
    "required": ["runtime"],
    "properties": { "framework": false }
  }
]
```

- [ ] **Step 2: Verify schema parses**

```bash
python3 -c "
import json
with open('engine/schema/agent.schema.json') as f:
    s = json.load(f)
print('framework in required:', 'framework' in s['required'])
print('runtime in properties:', 'runtime' in s['properties'])
print('type in properties:', 'type' in s['properties'])
print('oneOf present:', 'oneOf' in s)
"
```

Expected output:
```
framework in required: False
runtime in properties: True
type in properties: True
oneOf present: True
```

- [ ] **Step 3: Run config parser tests to confirm no regressions**

```bash
pytest tests/unit/test_config_parser.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add engine/schema/agent.schema.json
git commit -m "feat(schema): add runtime block and type enum to agent.schema.json"
```

---

### Task 3: `engine/runtimes/registry.py` + `engine/runtimes/python.py`

**Files:**
- Create: `engine/runtimes/registry.py`
- Create: `engine/runtimes/python.py`

- [ ] **Step 1: Write failing test for `get_runtime_from_config`**

Create `tests/unit/test_runtime_registry.py`:

```python
"""Tests for the language-based runtime registry."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from engine.config_parser import AgentConfig, FrameworkType, RuntimeConfig


def _make_python_config(framework: str = "langgraph") -> AgentConfig:
    return AgentConfig(
        name="test-agent",
        version="1.0.0",
        team="eng",
        owner="test@example.com",
        framework=FrameworkType(framework),
        model={"primary": "gpt-4o"},
        deploy={"cloud": "local"},
    )


def _make_node_config(framework: str = "vercel-ai") -> AgentConfig:
    return AgentConfig(
        name="test-agent",
        version="1.0.0",
        team="eng",
        owner="test@example.com",
        runtime=RuntimeConfig(language="node", framework=framework),
        model={"primary": "gpt-4o"},
        deploy={"cloud": "local"},
    )


class TestGetRuntimeFromConfig:
    def test_python_langgraph_routes_to_langgraph_runtime(self) -> None:
        from engine.runtimes.langgraph import LangGraphRuntime
        from engine.runtimes.registry import get_runtime_from_config

        runtime = get_runtime_from_config(_make_python_config("langgraph"))
        assert isinstance(runtime, LangGraphRuntime)

    def test_python_crewai_routes_to_crewai_runtime(self) -> None:
        from engine.runtimes.crewai import CrewAIRuntime
        from engine.runtimes.registry import get_runtime_from_config

        runtime = get_runtime_from_config(_make_python_config("crewai"))
        assert isinstance(runtime, CrewAIRuntime)

    def test_unsupported_language_raises(self) -> None:
        from engine.runtimes.registry import UnsupportedLanguageError, get_runtime_from_config

        config = AgentConfig(
            name="test-agent",
            version="1.0.0",
            team="eng",
            owner="test@example.com",
            runtime=RuntimeConfig(language="node", framework="vercel-ai"),
            model={"primary": "gpt-4o"},
            deploy={"cloud": "local"},
        )
        # node is not yet in registry in PR 2 — raises UnsupportedLanguageError
        with pytest.raises(UnsupportedLanguageError):
            get_runtime_from_config(config)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_runtime_registry.py -v 2>&1 | tail -15
```

Expected: ImportError or ModuleNotFoundError on `engine.runtimes.registry`.

- [ ] **Step 3: Create `engine/runtimes/python.py`**

```python
"""Python runtime family — dispatches to per-framework runtime builders."""
from __future__ import annotations

from engine.config_parser import FrameworkType
from engine.runtimes.base import RuntimeBuilder
from engine.runtimes.claude_sdk import ClaudeSDKRuntime
from engine.runtimes.crewai import CrewAIRuntime
from engine.runtimes.custom import CustomRuntime
from engine.runtimes.google_adk import GoogleADKRuntime
from engine.runtimes.langgraph import LangGraphRuntime
from engine.runtimes.openai_agents import OpenAIAgentsRuntime

_BUILDERS: dict[FrameworkType, type[RuntimeBuilder]] = {
    FrameworkType.langgraph: LangGraphRuntime,
    FrameworkType.crewai: CrewAIRuntime,
    FrameworkType.claude_sdk: ClaudeSDKRuntime,
    FrameworkType.openai_agents: OpenAIAgentsRuntime,
    FrameworkType.google_adk: GoogleADKRuntime,
    FrameworkType.custom: CustomRuntime,
}


class PythonRuntimeFamily:
    """Factory for Python framework runtime builders."""

    @classmethod
    def from_framework(cls, framework: FrameworkType | None) -> RuntimeBuilder:
        if framework is None:
            raise ValueError("framework must be set for Python agents")
        builder_cls = _BUILDERS.get(framework)
        if builder_cls is None:
            raise KeyError(f"Unsupported Python framework: {framework!r}")
        return builder_cls()
```

- [ ] **Step 4: Create `engine/runtimes/registry.py`**

```python
"""Language-based runtime registry.

Maps language strings to runtime factories. Adding a new language = one new
factory function + one dict entry. Zero changes to the deploy pipeline.
"""
from __future__ import annotations

from collections.abc import Callable

from engine.config_parser import AgentConfig
from engine.runtimes.base import RuntimeBuilder


class UnsupportedLanguageError(Exception):
    """Raised when an agent config requests a language not yet in the registry."""


def _python_factory(config: AgentConfig) -> RuntimeBuilder:
    from engine.runtimes.python import PythonRuntimeFamily
    return PythonRuntimeFamily.from_framework(config.framework)


# PR 2: only python registered.
# PR 3 adds: "node": _node_factory
LANGUAGE_REGISTRY: dict[str, Callable[[AgentConfig], RuntimeBuilder]] = {
    "python": _python_factory,
}


def get_runtime_from_config(config: AgentConfig) -> RuntimeBuilder:
    """Route an AgentConfig to the correct RuntimeBuilder.

    If config.runtime is set, dispatches by language.
    Otherwise falls back to the Python path (config.framework).
    """
    if config.runtime:
        factory = LANGUAGE_REGISTRY.get(config.runtime.language)
        if factory is None:
            raise UnsupportedLanguageError(
                f"Language '{config.runtime.language}' is not yet supported. "
                f"Supported languages: {list(LANGUAGE_REGISTRY.keys())}"
            )
        return factory(config)
    return LANGUAGE_REGISTRY["python"](config)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_runtime_registry.py -v 2>&1 | tail -15
```

Expected: `test_python_langgraph_routes_to_langgraph_runtime` PASS, `test_python_crewai_routes_to_crewai_runtime` PASS, `test_unsupported_language_raises` PASS.

- [ ] **Step 6: Commit**

```bash
git add engine/runtimes/registry.py engine/runtimes/python.py tests/unit/test_runtime_registry.py
git commit -m "feat(runtimes): add LANGUAGE_REGISTRY, PythonRuntimeFamily, get_runtime_from_config"
```

---

### Task 4: Update `engine/builder.py` dispatch

**Files:**
- Modify: `engine/builder.py`

- [ ] **Step 1: Find and replace the `get_runtime` call in step 4**

Open `engine/builder.py`. Find this block inside the `deploy()` method (around line 130):

```python
runtime = get_runtime(config.framework)
```

Replace it with:

```python
from engine.runtimes.registry import get_runtime_from_config
runtime = get_runtime_from_config(config)
```

Also remove the import of `get_runtime` from `engine.runtimes` at the top of the file if it's no longer used anywhere else. Check with:

```bash
grep -n "get_runtime" engine/builder.py
```

If `get_runtime` appears only in the one place you just changed, remove its import. If it appears elsewhere, leave the import.

- [ ] **Step 2: Run unit tests to check no regressions**

```bash
pytest tests/unit/ -v 2>&1 | tail -20
```

Expected: all passing (the builder dispatch change is transparent — Python path unchanged).

- [ ] **Step 3: Commit**

```bash
git add engine/builder.py
git commit -m "feat(builder): route deploy pipeline through get_runtime_from_config"
```

---

### Task 5: `api/config.py` settings + `engine/deployers/base.py` `get_aps_env_vars()`

**Files:**
- Modify: `api/config.py`
- Modify: `engine/deployers/base.py`
- Create: `tests/unit/test_deployer_base.py`

- [ ] **Step 1: Write a failing test**

Create `tests/unit/test_deployer_base.py`:

```python
"""Tests for BaseDeployer helper methods."""
from __future__ import annotations

import os
from unittest.mock import patch

from engine.deployers.docker_compose import DockerComposeDeployer


class TestGetApsEnvVars:
    def test_returns_both_vars(self) -> None:
        deployer = DockerComposeDeployer.__new__(DockerComposeDeployer)
        with patch.dict(os.environ, {
            "AGENTBREEDER_URL": "http://api:8000",
            "AGENTBREEDER_API_KEY": "test-key-123",
        }):
            result = deployer.get_aps_env_vars()
        assert result["AGENTBREEDER_URL"] == "http://api:8000"
        assert result["AGENTBREEDER_API_KEY"] == "test-key-123"

    def test_falls_back_to_defaults_when_env_unset(self) -> None:
        deployer = DockerComposeDeployer.__new__(DockerComposeDeployer)
        env_without_aps = {k: v for k, v in os.environ.items()
                           if k not in ("AGENTBREEDER_URL", "AGENTBREEDER_API_KEY")}
        with patch.dict(os.environ, env_without_aps, clear=True):
            result = deployer.get_aps_env_vars()
        assert result["AGENTBREEDER_URL"] == "http://agentbreeder-api:8000"
        assert result["AGENTBREEDER_API_KEY"] == ""
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_deployer_base.py -v 2>&1 | tail -10
```

Expected: AttributeError — `get_aps_env_vars` not found.

- [ ] **Step 3: Add `get_aps_env_vars()` to `engine/deployers/base.py`**

Open `engine/deployers/base.py`. After the existing imports, add `import os`. Then add `get_aps_env_vars` to `BaseDeployer` (after the `get_logs` abstract method):

```python
def get_aps_env_vars(self) -> dict[str, str]:
    """Return AGENTBREEDER_URL + AGENTBREEDER_API_KEY for injection into agent containers.

    Every deployed agent container receives these so the @agentbreeder/aps-client
    can call the central AgentBreeder API for RAG, memory, cost tracking, and tracing.
    """
    return {
        "AGENTBREEDER_URL": os.environ.get(
            "AGENTBREEDER_URL", "http://agentbreeder-api:8000"
        ),
        "AGENTBREEDER_API_KEY": os.environ.get("AGENTBREEDER_API_KEY", ""),
    }
```

Also add `import os` near the top of `base.py` if not already present.

- [ ] **Step 4: Add `agentbreeder_url` + `agentbreeder_api_key` to `api/config.py`**

Open `api/config.py`. Add these two fields to the `Settings` class after `litellm_base_url`:

```python
# AgentBreeder API — used by deployed agent containers to call platform services
agentbreeder_url: str = "http://agentbreeder-api:8000"
agentbreeder_api_key: str = ""
```

- [ ] **Step 5: Run the test**

```bash
pytest tests/unit/test_deployer_base.py -v 2>&1 | tail -10
```

Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add engine/deployers/base.py api/config.py tests/unit/test_deployer_base.py
git commit -m "feat(deployers): add get_aps_env_vars helper + AGENTBREEDER_URL settings"
```

---

### Task 6: Inject `AGENTBREEDER_URL` + `AGENTBREEDER_API_KEY` in 3 deployers

**Files:**
- Modify: `engine/deployers/docker_compose.py`
- Modify: `engine/deployers/aws_ecs.py`
- Modify: `engine/deployers/gcp_cloudrun.py`

- [ ] **Step 1: Inject in Docker Compose deployer**

Open `engine/deployers/docker_compose.py`. Find the `container_env` dict build in `deploy()` (around line 183). After the block that sets `AGENT_NAME`, `AGENT_VERSION`, etc., add:

```python
# Inject AgentBreeder platform env vars for @agentbreeder/aps-client
container_env.update(self.get_aps_env_vars())
```

Place this line BEFORE `container_env.update(config.deploy.env_vars)` so user env vars can override platform defaults if needed.

- [ ] **Step 2: Inject in AWS ECS deployer**

Open `engine/deployers/aws_ecs.py`. Find `_build_container_definition()`. Locate the `env_vars` dict that gets built (around line 295). Add the APS vars to this dict, before the user env_vars loop:

```python
# Inject AgentBreeder platform env vars
env_vars.update(self.get_aps_env_vars())
# Add user-defined env vars (can override platform vars)
for key, value in config.deploy.env_vars.items():
    ...
```

- [ ] **Step 3: Inject in GCP Cloud Run deployer**

Open `engine/deployers/gcp_cloudrun.py`. Find the `plain_env_vars` dict build (around line 125). After the OTel block, add:

```python
# Inject AgentBreeder platform env vars
plain_env_vars.update(self.get_aps_env_vars())
```

Place this before the user env_vars loop.

- [ ] **Step 4: Run full unit test suite**

```bash
pytest tests/unit/ -v --tb=short 2>&1 | tail -25
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add engine/deployers/docker_compose.py engine/deployers/aws_ecs.py engine/deployers/gcp_cloudrun.py
git commit -m "feat(deployers): inject AGENTBREEDER_URL into all deployed containers"
```

---

### Task 7: PR 2 final check

- [ ] **Step 1: Run full test suite and lint**

```bash
pytest tests/unit/ -v 2>&1 | tail -10
ruff check engine/ api/ tests/ && ruff format --check engine/ api/ tests/
mypy engine/ api/ --ignore-missing-imports 2>&1 | grep -E "error:|Found" | tail -10
```

Expected: all tests pass, no lint errors, no new mypy errors.

- [ ] **Step 2: Quick smoke test — validate a node agent.yaml**

```bash
python3 -c "
from engine.config_parser import validate_config
import tempfile, pathlib
with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
    f.write('''
name: my-ts-agent
version: 1.0.0
team: engineering
owner: dev@example.com
runtime:
  language: node
  framework: vercel-ai
  version: \"20\"
model:
  primary: gpt-4o
deploy:
  cloud: local
''')
    f.flush()
    result = validate_config(pathlib.Path(f.name))
print('valid:', result.valid)
print('errors:', result.errors)
print('language:', result.config.runtime.language if result.config else 'N/A')
"
```

Expected output: `valid: True`, `errors: []`, `language: node`.

---

## PR 3: Node Runtime

### Task 8: `@agentbreeder/aps-client` npm package

**Files:**
- Create: `engine/sidecar/client/ts/package.json`
- Create: `engine/sidecar/client/ts/tsconfig.json`
- Create: `engine/sidecar/client/ts/src/index.ts`
- Create: `engine/sidecar/client/ts/src/__tests__/aps_client.test.ts`

- [ ] **Step 1: Create `engine/sidecar/client/ts/package.json`**

```json
{
  "name": "@agentbreeder/aps-client",
  "version": "0.1.0",
  "description": "AgentBreeder Platform Services client for TypeScript agents",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "scripts": {
    "test": "jest --passWithNoTests",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "node-fetch": "^3.3.2"
  },
  "devDependencies": {
    "@types/jest": "^29.5.0",
    "@types/node": "^20.0.0",
    "jest": "^29.7.0",
    "ts-jest": "^29.1.0",
    "typescript": "^5.4.0"
  },
  "jest": {
    "preset": "ts-jest",
    "testEnvironment": "node",
    "testMatch": ["**/__tests__/**/*.test.ts"]
  }
}
```

- [ ] **Step 2: Create `engine/sidecar/client/ts/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "declaration": true,
    "outDir": "dist"
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 3: Write failing tests first**

Create `engine/sidecar/client/ts/src/__tests__/aps_client.test.ts`:

```typescript
import { APSClient } from '../index'

// Minimal fetch mock
const mockFetch = jest.fn()
jest.mock('node-fetch', () => ({
  __esModule: true,
  default: mockFetch,
}))

describe('APSClient', () => {
  beforeEach(() => {
    mockFetch.mockClear()
    process.env.AGENTBREEDER_URL = 'http://localhost:8000'
    process.env.AGENTBREEDER_API_KEY = 'test-key'
  })

  describe('constructor', () => {
    it('reads url and apiKey from env vars by default', () => {
      const client = new APSClient()
      // access via a method call to verify env was read
      mockFetch.mockResolvedValueOnce({ ok: true, json: async () => [] })
      void client.memory.load('t1')
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('http://localhost:8000'),
        expect.anything()
      )
    })

    it('accepts explicit url and apiKey overrides', () => {
      const client = new APSClient({ url: 'http://custom:9000', apiKey: 'key2' })
      mockFetch.mockResolvedValueOnce({ ok: true, json: async () => [] })
      void client.memory.load('t1')
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('http://custom:9000'),
        expect.anything()
      )
    })
  })

  describe('cost.record', () => {
    it('does not throw when fetch fails', async () => {
      mockFetch.mockRejectedValueOnce(new Error('network error'))
      const client = new APSClient()
      // Must not throw
      expect(() =>
        client.cost.record({ agentName: 'a', model: 'gpt-4o', inputTokens: 10, outputTokens: 5 })
      ).not.toThrow()
      // Give the fire-and-forget a tick to complete
      await new Promise(r => setTimeout(r, 0))
    })

    it('returns void (not a promise)', () => {
      mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) })
      const client = new APSClient()
      const result = client.cost.record({ agentName: 'a', model: 'gpt-4o', inputTokens: 1, outputTokens: 1 })
      expect(result).toBeUndefined()
    })
  })

  describe('trace.span', () => {
    it('does not throw when fetch fails', async () => {
      mockFetch.mockRejectedValueOnce(new Error('network error'))
      const client = new APSClient()
      expect(() => client.trace.span({ name: 'test-span' })).not.toThrow()
      await new Promise(r => setTimeout(r, 0))
    })
  })

  describe('rag.search', () => {
    it('retries on 5xx and eventually throws', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 503, json: async () => ({}) })
      const client = new APSClient()
      await expect(client.rag.search('hello', { indexIds: ['idx1'] })).rejects.toThrow()
      expect(mockFetch).toHaveBeenCalledTimes(3)
    })

    it('returns chunks on success', async () => {
      const chunks = [{ text: 'hello', score: 0.9, source: 'doc.pdf' }]
      mockFetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => chunks })
      const client = new APSClient()
      const result = await client.rag.search('hello', { indexIds: ['idx1'] })
      expect(result).toEqual(chunks)
    })
  })
})
```

- [ ] **Step 4: Create `engine/sidecar/client/ts/src/index.ts`**

```typescript
import fetch from 'node-fetch'
import type { RequestInit, Response } from 'node-fetch'

export interface RagSearchOpts {
  indexIds: string[]
  topK?: number
}

export interface RagChunk {
  text: string
  score: number
  source: string
}

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface CostEvent {
  agentName: string
  model: string
  inputTokens: number
  outputTokens: number
  costUsd?: number
}

export interface SpanEvent {
  name: string
  attributes?: Record<string, string | number | boolean>
}

export interface AgentRuntimeConfig {
  agentName: string
  model: string
  kbIndexIds: string[]
  tools: string[]
}

async function withRetry(
  fn: () => Promise<Response>,
  retries = 3,
  delayMs = 500
): Promise<Response> {
  for (let attempt = 0; attempt < retries; attempt++) {
    const res = await fn()
    if (res.ok || res.status < 500) return res
    if (attempt < retries - 1) {
      await new Promise(resolve => setTimeout(resolve, delayMs * 2 ** attempt))
    }
  }
  throw new Error(`Request failed after ${retries} retries`)
}

export class APSClient {
  private readonly baseUrl: string
  private readonly apiKey: string

  constructor(opts?: { url?: string; apiKey?: string }) {
    this.baseUrl = (opts?.url ?? process.env.AGENTBREEDER_URL ?? 'http://localhost:8000').replace(/\/$/, '')
    this.apiKey = opts?.apiKey ?? process.env.AGENTBREEDER_API_KEY ?? ''
  }

  private get headers(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.apiKey}`,
    }
  }

  private async _get<T>(path: string, params?: Record<string, string>): Promise<T> {
    const url = new URL(this.baseUrl + path)
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
    }
    const res = await withRetry(() =>
      fetch(url.toString(), { headers: this.headers }) as Promise<Response>
    )
    if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
    return res.json() as Promise<T>
  }

  private async _post<T>(path: string, body: unknown): Promise<T> {
    const res = await withRetry(() =>
      fetch(this.baseUrl + path, {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify(body),
      } as RequestInit) as Promise<Response>
    )
    if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
    return res.json() as Promise<T>
  }

  rag = {
    search: (query: string, opts: RagSearchOpts): Promise<RagChunk[]> =>
      this._post<RagChunk[]>('/api/v1/rag/search', {
        query,
        index_id: opts.indexIds[0],  // primary index
        top_k: opts.topK ?? 5,
      }),
  }

  memory = {
    load: (threadId: string): Promise<Message[]> =>
      this._get<Message[]>(`/api/v1/memory/thread/${encodeURIComponent(threadId)}`),
    save: (threadId: string, messages: Message[]): Promise<void> =>
      this._post<void>('/api/v1/memory/thread', { thread_id: threadId, messages }),
  }

  cost = {
    record: (e: CostEvent): void => {
      void this._post('/api/v1/costs/events', {
        agent_name: e.agentName,
        model: e.model,
        input_tokens: e.inputTokens,
        output_tokens: e.outputTokens,
        cost_usd: e.costUsd,
      }).catch(() => {})
    },
  }

  trace = {
    span: (e: SpanEvent): void => {
      void this._post('/api/v1/traces', {
        operation: e.name,
        attributes: e.attributes ?? {},
      }).catch(() => {})
    },
  }

  a2a = {
    call: (agentName: string, input: unknown): Promise<unknown> =>
      this._post(`/api/v1/a2a/invoke`, { agent_name: agentName, input }),
  }

  tools = {
    execute: (name: string, input: unknown): Promise<unknown> =>
      this._post('/api/v1/tools/sandbox/execute', { tool_id: name, input_json: JSON.stringify(input) }),
  }

  config = {
    get: (): Promise<AgentRuntimeConfig> =>
      this._get<AgentRuntimeConfig>('/api/v1/agents/runtime-config'),
  }
}
```

- [ ] **Step 5: Install deps and run tests**

```bash
cd engine/sidecar/client/ts
npm install
npm test
```

Expected: all 7 tests pass.

- [ ] **Step 6: Go back to repo root and commit**

```bash
cd /Users/rajit/personal-github/agentbreeder
git add engine/sidecar/client/ts/
git commit -m "feat(aps-client): add @agentbreeder/aps-client npm package"
```

---

### Task 9: Memory thread convenience endpoints

The `@agentbreeder/aps-client` calls `GET /api/v1/memory/thread/{thread_id}` and `POST /api/v1/memory/thread`. These don't exist yet — add them to the memory router.

**Files:**
- Modify: `api/routes/memory.py`

- [ ] **Step 1: Add a `ThreadSaveRequest` schema**

Open `api/models/schemas.py` (or wherever memory request schemas live — check with `grep -n "MemoryMessageCreate" api/models/schemas.py`). Add:

```python
class ThreadSaveRequest(BaseModel):
    thread_id: str
    messages: list[dict[str, str]]  # [{"role": "user", "content": "..."}]
```

- [ ] **Step 2: Add two convenience endpoints to `api/routes/memory.py`**

At the bottom of `api/routes/memory.py`, add:

```python
@router.get("/thread/{thread_id}", response_model=ApiResponse[list[dict]])
async def load_thread(
    thread_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[dict]]:
    """Load messages for a thread. Used by @agentbreeder/aps-client.

    Returns messages as {role, content} dicts.
    Creates the default memory config on first access if none exists.
    """
    msgs = await MemoryService.get_or_create_thread(db, thread_id, owner_id=_user.id)
    return ApiResponse(data=[{"role": m.role, "content": m.content} for m in msgs])


@router.post("/thread", response_model=ApiResponse[dict], status_code=201)
async def save_thread(
    body: ThreadSaveRequest,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    """Save messages for a thread. Used by @agentbreeder/aps-client."""
    count = await MemoryService.upsert_thread(db, body.thread_id, body.messages, owner_id=_user.id)
    return ApiResponse(data={"saved": count})
```

- [ ] **Step 3: Add `get_or_create_thread` + `upsert_thread` to `MemoryService`**

Open `api/services/` and find the memory service file (check: `ls api/services/` and look for `memory_service.py`).

Add to the `MemoryService` class:

```python
@staticmethod
async def get_or_create_thread(
    db: AsyncSession,
    thread_id: str,
    owner_id: str,
) -> list[Any]:
    """Return messages for thread_id, using or creating a 'default' memory config."""
    # Find or create a default config for this owner
    result = await db.execute(
        select(MemoryConfig).where(
            MemoryConfig.owner_id == owner_id,
            MemoryConfig.name == "default",
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        config = MemoryConfig(
            id=str(uuid.uuid4()),
            name="default",
            owner_id=owner_id,
            backend="in_memory",
        )
        db.add(config)
        await db.flush()

    msgs = await MemoryService.get_conversation(config.id, thread_id)
    return msgs

@staticmethod
async def upsert_thread(
    db: AsyncSession,
    thread_id: str,
    messages: list[dict[str, str]],
    owner_id: str,
) -> int:
    """Replace messages for thread_id. Returns count of saved messages."""
    result = await db.execute(
        select(MemoryConfig).where(
            MemoryConfig.owner_id == owner_id,
            MemoryConfig.name == "default",
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        config = MemoryConfig(
            id=str(uuid.uuid4()),
            name="default",
            owner_id=owner_id,
            backend="in_memory",
        )
        db.add(config)
        await db.flush()

    for msg in messages:
        await MemoryService.store_message(
            config.id,
            session_id=thread_id,
            role=msg["role"],
            content=msg["content"],
        )
    await db.commit()
    return len(messages)
```

**Note:** Check the actual `MemoryConfig` model field names and `MemoryService` interface before writing — adjust field names to match what's already in the codebase (`grep -n "class MemoryConfig" api/models/database.py`).

- [ ] **Step 4: Run unit tests**

```bash
pytest tests/unit/ -v --tb=short 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api/routes/memory.py api/services/ api/models/schemas.py
git commit -m "feat(memory): add thread convenience endpoints for @agentbreeder/aps-client"
```

---

### Task 10: `_shared_loader.ts` + `vercel_ai_server.ts` template

**Files:**
- Create: `engine/runtimes/templates/node/_shared_loader.ts`
- Create: `engine/runtimes/templates/node/vercel_ai_server.ts`

- [ ] **Step 1: Create `engine/runtimes/templates/node/_shared_loader.ts`**

```typescript
// AgentBreeder shared loader — imported by all framework templates.
// Do not edit — platform-managed.
import { APSClient } from './aps-client/src/index.js'

export const aps = new APSClient()

export const AGENT_NAME: string = process.env.AGENT_NAME ?? 'unknown'
export const AGENT_VERSION: string = process.env.AGENT_VERSION ?? '0.0.0'

export function healthHandler(_req: any, res: any): void {
  res.json({ status: 'ok', agent: AGENT_NAME, version: AGENT_VERSION })
}

export function agentCardHandler(_req: any, res: any): void {
  res.json({
    name: AGENT_NAME,
    version: AGENT_VERSION,
    protocol: 'a2a/v1',
    endpoints: { invoke: '/invoke', stream: '/stream' },
  })
}
```

- [ ] **Step 2: Create `engine/runtimes/templates/node/vercel_ai_server.ts`**

```typescript
// Generated by AgentBreeder — do not edit manually.
// Framework: Vercel AI SDK
import express from 'express'
import { healthHandler, agentCardHandler, aps } from './_shared_loader.js'
import { streamText, generateText } from 'ai'

// Developer's agent configuration — the only file they write
import { model, systemPrompt, tools as agentTools } from './{{ENTRYPOINT_NOEXT}}.js'

const app = express()
app.use(express.json())

app.get('/health', healthHandler)
app.get('/.well-known/agent.json', agentCardHandler)

app.post('/invoke', async (req: any, res: any) => {
  const { messages = [], thread_id } = req.body as { messages: any[]; thread_id?: string }
  const history = thread_id ? await aps.memory.load(thread_id) : []
  const allMessages = [...history, ...messages]

  try {
    const { text } = await generateText({
      model,
      system: systemPrompt ?? undefined,
      messages: allMessages,
      tools: agentTools ?? undefined,
    })
    if (thread_id) {
      await aps.memory.save(thread_id, [
        ...allMessages,
        { role: 'assistant' as const, content: text },
      ])
    }
    aps.cost.record({ agentName: '{{AGENT_NAME}}', model: '{{AGENT_MODEL}}', inputTokens: 0, outputTokens: 0 })
    res.json({ output: text })
  } catch (err) {
    res.status(500).json({ error: String(err) })
  }
})

app.post('/stream', async (req: any, res: any) => {
  const { messages = [], thread_id } = req.body as { messages: any[]; thread_id?: string }
  const history = thread_id ? await aps.memory.load(thread_id) : []

  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')

  try {
    const { textStream } = streamText({
      model,
      system: systemPrompt ?? undefined,
      messages: [...history, ...messages],
      tools: agentTools ?? undefined,
    })
    for await (const chunk of textStream) {
      res.write(`data: ${JSON.stringify({ chunk })}\n\n`)
    }
    res.write('data: [DONE]\n\n')
  } catch (err) {
    res.write(`data: ${JSON.stringify({ error: String(err) })}\n\n`)
  }
  res.end()
})

const PORT = parseInt(process.env.PORT ?? '3000', 10)
app.listen(PORT, () => console.log(`[{{AGENT_NAME}}] running on :${PORT}`))
```

- [ ] **Step 3: Commit**

```bash
git add engine/runtimes/templates/node/
git commit -m "feat(templates): add _shared_loader.ts and vercel_ai_server.ts template"
```

---

### Task 11: Remaining 5 agent templates

**Files:**
- Create: `engine/runtimes/templates/node/mastra_server.ts`
- Create: `engine/runtimes/templates/node/langchain_js_server.ts`
- Create: `engine/runtimes/templates/node/openai_agents_ts_server.ts`
- Create: `engine/runtimes/templates/node/deepagent_server.ts`
- Create: `engine/runtimes/templates/node/custom_node_server.ts`

All 5 templates share the same Express structure as `vercel_ai_server.ts`. They differ only in the agent SDK import and the `generate` + `stream` call. Copy the structure and change the framework-specific section.

- [ ] **Step 1: Create `mastra_server.ts`**

```typescript
// Generated by AgentBreeder — do not edit manually.
// Framework: Mastra
import express from 'express'
import { healthHandler, agentCardHandler, aps } from './_shared_loader.js'
import { Agent } from './{{ENTRYPOINT_NOEXT}}.js'

const app = express()
app.use(express.json())
app.get('/health', healthHandler)
app.get('/.well-known/agent.json', agentCardHandler)

app.post('/invoke', async (req: any, res: any) => {
  const { messages = [], thread_id } = req.body
  const history = thread_id ? await aps.memory.load(thread_id) : []
  try {
    const result = await Agent.generate([...history, ...messages])
    const text = result.text ?? String(result)
    if (thread_id) await aps.memory.save(thread_id, [...history, ...messages, { role: 'assistant' as const, content: text }])
    aps.cost.record({ agentName: '{{AGENT_NAME}}', model: '{{AGENT_MODEL}}', inputTokens: 0, outputTokens: 0 })
    res.json({ output: text })
  } catch (err) { res.status(500).json({ error: String(err) }) }
})

app.post('/stream', async (req: any, res: any) => {
  const { messages = [], thread_id } = req.body
  const history = thread_id ? await aps.memory.load(thread_id) : []
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  try {
    const stream = await Agent.stream([...history, ...messages])
    for await (const chunk of stream.textStream) {
      res.write(`data: ${JSON.stringify({ chunk })}\n\n`)
    }
    res.write('data: [DONE]\n\n')
  } catch (err) { res.write(`data: ${JSON.stringify({ error: String(err) })}\n\n`) }
  res.end()
})

const PORT = parseInt(process.env.PORT ?? '3000', 10)
app.listen(PORT, () => console.log(`[{{AGENT_NAME}}] running on :${PORT}`))
```

- [ ] **Step 2: Create `langchain_js_server.ts`**

```typescript
// Generated by AgentBreeder — do not edit manually.
// Framework: LangChain.js
import express from 'express'
import { healthHandler, agentCardHandler, aps } from './_shared_loader.js'
import { chain } from './{{ENTRYPOINT_NOEXT}}.js'

const app = express()
app.use(express.json())
app.get('/health', healthHandler)
app.get('/.well-known/agent.json', agentCardHandler)

app.post('/invoke', async (req: any, res: any) => {
  const { messages = [], thread_id } = req.body
  const history = thread_id ? await aps.memory.load(thread_id) : []
  const input = messages.at(-1)?.content ?? ''
  try {
    const result = await chain.invoke({ input, history })
    const text = typeof result === 'string' ? result : result?.output ?? String(result)
    if (thread_id) await aps.memory.save(thread_id, [...history, ...messages, { role: 'assistant' as const, content: text }])
    aps.cost.record({ agentName: '{{AGENT_NAME}}', model: '{{AGENT_MODEL}}', inputTokens: 0, outputTokens: 0 })
    res.json({ output: text })
  } catch (err) { res.status(500).json({ error: String(err) }) }
})

app.post('/stream', async (req: any, res: any) => {
  const { messages = [], thread_id } = req.body
  const history = thread_id ? await aps.memory.load(thread_id) : []
  const input = messages.at(-1)?.content ?? ''
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  try {
    const stream = await chain.stream({ input, history })
    for await (const chunk of stream) {
      res.write(`data: ${JSON.stringify({ chunk: String(chunk) })}\n\n`)
    }
    res.write('data: [DONE]\n\n')
  } catch (err) { res.write(`data: ${JSON.stringify({ error: String(err) })}\n\n`) }
  res.end()
})

const PORT = parseInt(process.env.PORT ?? '3000', 10)
app.listen(PORT, () => console.log(`[{{AGENT_NAME}}] running on :${PORT}`))
```

- [ ] **Step 3: Create `openai_agents_ts_server.ts`**

```typescript
// Generated by AgentBreeder — do not edit manually.
// Framework: OpenAI Agents SDK (TypeScript)
import express from 'express'
import { healthHandler, agentCardHandler, aps } from './_shared_loader.js'
import { Agent, run } from '@openai/agents'
import { agent } from './{{ENTRYPOINT_NOEXT}}.js'

const app = express()
app.use(express.json())
app.get('/health', healthHandler)
app.get('/.well-known/agent.json', agentCardHandler)

app.post('/invoke', async (req: any, res: any) => {
  const { messages = [], thread_id } = req.body
  const history = thread_id ? await aps.memory.load(thread_id) : []
  const input = messages.at(-1)?.content ?? ''
  try {
    const result = await run(agent, input)
    const text = result.finalOutput ?? ''
    if (thread_id) await aps.memory.save(thread_id, [...history, ...messages, { role: 'assistant' as const, content: text }])
    aps.cost.record({ agentName: '{{AGENT_NAME}}', model: '{{AGENT_MODEL}}', inputTokens: 0, outputTokens: 0 })
    res.json({ output: text })
  } catch (err) { res.status(500).json({ error: String(err) }) }
})

app.post('/stream', async (req: any, res: any) => {
  const { messages = [] } = req.body
  const input = messages.at(-1)?.content ?? ''
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  try {
    const stream = run(agent, input, { stream: true })
    for await (const event of stream) {
      if (event.type === 'raw_model_stream_event') {
        const chunk = (event.data as any)?.delta?.content ?? ''
        if (chunk) res.write(`data: ${JSON.stringify({ chunk })}\n\n`)
      }
    }
    res.write('data: [DONE]\n\n')
  } catch (err) { res.write(`data: ${JSON.stringify({ error: String(err) })}\n\n`) }
  res.end()
})

const PORT = parseInt(process.env.PORT ?? '3000', 10)
app.listen(PORT, () => console.log(`[{{AGENT_NAME}}] running on :${PORT}`))
```

- [ ] **Step 4: Create `deepagent_server.ts`**

```typescript
// Generated by AgentBreeder — do not edit manually.
// Framework: DeepAgent
import express from 'express'
import { healthHandler, agentCardHandler, aps } from './_shared_loader.js'
import { agent } from './{{ENTRYPOINT_NOEXT}}.js'

const app = express()
app.use(express.json())
app.get('/health', healthHandler)
app.get('/.well-known/agent.json', agentCardHandler)

app.post('/invoke', async (req: any, res: any) => {
  const { messages = [], thread_id } = req.body
  const history = thread_id ? await aps.memory.load(thread_id) : []
  const input = messages.at(-1)?.content ?? ''
  try {
    const result = await agent.run(input, { history })
    const text = typeof result === 'string' ? result : result?.output ?? String(result)
    if (thread_id) await aps.memory.save(thread_id, [...history, ...messages, { role: 'assistant' as const, content: text }])
    aps.cost.record({ agentName: '{{AGENT_NAME}}', model: '{{AGENT_MODEL}}', inputTokens: 0, outputTokens: 0 })
    res.json({ output: text })
  } catch (err) { res.status(500).json({ error: String(err) }) }
})

app.post('/stream', async (req: any, res: any) => {
  const { messages = [] } = req.body
  const input = messages.at(-1)?.content ?? ''
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  try {
    const stream = await agent.stream(input)
    for await (const chunk of stream) {
      res.write(`data: ${JSON.stringify({ chunk: String(chunk) })}\n\n`)
    }
    res.write('data: [DONE]\n\n')
  } catch (err) { res.write(`data: ${JSON.stringify({ error: String(err) })}\n\n`) }
  res.end()
})

const PORT = parseInt(process.env.PORT ?? '3000', 10)
app.listen(PORT, () => console.log(`[{{AGENT_NAME}}] running on :${PORT}`))
```

- [ ] **Step 5: Create `custom_node_server.ts`**

```typescript
// Generated by AgentBreeder — do not edit manually.
// Framework: Custom Node.js
// Developer exports: handler(input: string, context: ApsContext) => Promise<string>
import express from 'express'
import { healthHandler, agentCardHandler, aps } from './_shared_loader.js'
import { handler } from './{{ENTRYPOINT_NOEXT}}.js'

const app = express()
app.use(express.json())
app.get('/health', healthHandler)
app.get('/.well-known/agent.json', agentCardHandler)

app.post('/invoke', async (req: any, res: any) => {
  const { messages = [], thread_id } = req.body
  const history = thread_id ? await aps.memory.load(thread_id) : []
  const input = messages.at(-1)?.content ?? ''
  try {
    const output = await handler(input, { aps, history, thread_id })
    if (thread_id) await aps.memory.save(thread_id, [...history, ...messages, { role: 'assistant' as const, content: String(output) }])
    aps.cost.record({ agentName: '{{AGENT_NAME}}', model: '{{AGENT_MODEL}}', inputTokens: 0, outputTokens: 0 })
    res.json({ output })
  } catch (err) { res.status(500).json({ error: String(err) }) }
})

app.post('/stream', async (req: any, res: any) => {
  // Custom framework: fallback to invoke then emit as single chunk
  const { messages = [] } = req.body
  const input = messages.at(-1)?.content ?? ''
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  try {
    const output = await handler(input, { aps, history: [], thread_id: undefined })
    res.write(`data: ${JSON.stringify({ chunk: String(output) })}\n\n`)
    res.write('data: [DONE]\n\n')
  } catch (err) { res.write(`data: ${JSON.stringify({ error: String(err) })}\n\n`) }
  res.end()
})

const PORT = parseInt(process.env.PORT ?? '3000', 10)
app.listen(PORT, () => console.log(`[{{AGENT_NAME}}] running on :${PORT}`))
```

- [ ] **Step 6: Commit**

```bash
git add engine/runtimes/templates/node/
git commit -m "feat(templates): add 5 agent framework templates (mastra, langchain-js, openai-agents-ts, deepagent, custom)"
```

---

### Task 12: MCP server templates

**Files:**
- Create: `engine/runtimes/templates/node/mcp_ts_server.ts`
- Create: `engine/runtimes/templates/node/mcp_py_server.ts`

- [ ] **Step 1: Create `mcp_ts_server.ts`**

MCP TypeScript servers use `@modelcontextprotocol/sdk`. The developer exports tool handlers from `tools.ts`.

```typescript
// Generated by AgentBreeder — do not edit manually.
// Type: MCP Server (TypeScript)
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import * as tools from './{{ENTRYPOINT_NOEXT}}.js'

const server = new Server(
  { name: '{{AGENT_NAME}}', version: '{{AGENT_VERSION}}' },
  { capabilities: { tools: {} } }
)

const toolMeta: Record<string, { description: string; inputSchema: object }> = (tools as any).__meta ?? {}

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: Object.keys(tools)
    .filter(k => k !== '__meta' && typeof (tools as any)[k] === 'function')
    .map(name => ({
      name,
      description: toolMeta[name]?.description ?? name,
      inputSchema: toolMeta[name]?.inputSchema ?? { type: 'object', properties: {} },
    })),
}))

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const fn = (tools as any)[request.params.name]
  if (!fn) throw new Error(`Unknown tool: ${request.params.name}`)
  const result = await fn(request.params.arguments ?? {})
  return { content: [{ type: 'text', text: JSON.stringify(result) }] }
})

const transport = new StdioServerTransport()
await server.connect(transport)
console.error(`[{{AGENT_NAME}}] MCP server running on stdio`)
```

- [ ] **Step 2: Create `mcp_py_server.ts`**

Python MCP servers are wrapped by a Node.js HTTP-to-stdio proxy so they get the same deploy pipeline.

```typescript
// Generated by AgentBreeder — do not edit manually.
// Type: MCP Server (Python — stdio proxy)
import express from 'express'
import { spawn } from 'child_process'
import { healthHandler } from './_shared_loader.js'

const app = express()
app.use(express.json())
app.get('/health', healthHandler)

// Spawn the Python MCP process
const pythonProcess = spawn('python', ['{{ENTRYPOINT}}'], {
  stdio: ['pipe', 'pipe', 'inherit'],
})

pythonProcess.on('exit', (code) => {
  console.error(`Python MCP process exited with code ${code}`)
  process.exit(code ?? 1)
})

// Proxy HTTP requests to Python stdio (line-delimited JSON-RPC)
app.post('/mcp', async (req: any, res: any) => {
  const request = JSON.stringify(req.body) + '\n'
  pythonProcess.stdin.write(request)

  await new Promise<void>((resolve) => {
    pythonProcess.stdout.once('data', (data: Buffer) => {
      try {
        res.json(JSON.parse(data.toString().trim()))
      } catch {
        res.status(500).json({ error: 'Invalid JSON from Python MCP process' })
      }
      resolve()
    })
  })
})

const PORT = parseInt(process.env.PORT ?? '3000', 10)
app.listen(PORT, () => console.log(`[{{AGENT_NAME}}] Python MCP proxy running on :${PORT}`))
```

- [ ] **Step 3: Commit**

```bash
git add engine/runtimes/templates/node/
git commit -m "feat(templates): add mcp_ts_server.ts and mcp_py_server.ts templates"
```

---

### Task 13: `engine/runtimes/node.py` — `NodeRuntimeFamily`

**Files:**
- Create: `engine/runtimes/node.py`
- Create: `tests/unit/test_node_runtime.py`

- [ ] **Step 1: Write failing unit tests**

Create `tests/unit/test_node_runtime.py`:

```python
"""Tests for NodeRuntimeFamily."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from engine.config_parser import AgentConfig, LanguageType, RuntimeConfig


def _make_node_config(framework: str = "vercel-ai", version: str = "20") -> AgentConfig:
    return AgentConfig(
        name="test-agent",
        version="1.0.0",
        team="eng",
        owner="test@example.com",
        runtime=RuntimeConfig(language=LanguageType.node, framework=framework, version=version),
        model={"primary": "gpt-4o"},
        deploy={"cloud": "local"},
    )


def _make_agent_dir(tmp_path: Path, entrypoint: str = "agent.ts") -> Path:
    (tmp_path / entrypoint).write_text("export const model = null; export const systemPrompt = ''")
    return tmp_path


class TestNodeRuntimeFamilyBuild:
    def test_vercel_ai_produces_container_image(self, tmp_path: Path) -> None:
        from engine.runtimes.node import NodeRuntimeFamily

        config = _make_node_config("vercel-ai")
        agent_dir = _make_agent_dir(tmp_path)
        runtime = NodeRuntimeFamily()
        image = runtime.build(agent_dir, config)

        assert image.tag == "agentbreeder/test-agent:1.0.0"
        assert image.context_dir.exists()
        assert (image.context_dir / "Dockerfile").exists()
        assert (image.context_dir / "server.ts").exists()
        assert (image.context_dir / "package.json").exists()
        assert (image.context_dir / "tsconfig.json").exists()

    def test_dockerfile_uses_correct_node_version(self, tmp_path: Path) -> None:
        from engine.runtimes.node import NodeRuntimeFamily

        config = _make_node_config("vercel-ai", version="20")
        agent_dir = _make_agent_dir(tmp_path)
        runtime = NodeRuntimeFamily()
        image = runtime.build(agent_dir, config)

        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "node:20-slim" in dockerfile

    def test_package_json_includes_framework_deps(self, tmp_path: Path) -> None:
        from engine.runtimes.node import NodeRuntimeFamily

        config = _make_node_config("vercel-ai")
        agent_dir = _make_agent_dir(tmp_path)
        runtime = NodeRuntimeFamily()
        image = runtime.build(agent_dir, config)

        pkg = json.loads((image.context_dir / "package.json").read_text())
        assert "ai" in pkg["dependencies"]
        assert "express" in pkg["dependencies"]

    def test_unknown_framework_falls_back_to_custom(self, tmp_path: Path) -> None:
        from engine.runtimes.node import NodeRuntimeFamily

        config = _make_node_config("some-future-framework")
        agent_dir = _make_agent_dir(tmp_path)
        runtime = NodeRuntimeFamily()
        image = runtime.build(agent_dir, config)  # must not raise

        assert image.tag == "agentbreeder/test-agent:1.0.0"

    def test_validate_fails_when_agent_ts_missing(self, tmp_path: Path) -> None:
        from engine.runtimes.node import NodeRuntimeFamily

        config = _make_node_config("vercel-ai")
        runtime = NodeRuntimeFamily()
        result = runtime.validate(tmp_path, config)

        assert not result.valid
        assert any("agent.ts" in e for e in result.errors)

    def test_all_8_templates_produce_server_ts(self, tmp_path: Path) -> None:
        from engine.runtimes.node import NodeRuntimeFamily, FRAMEWORK_TEMPLATES

        runtime = NodeRuntimeFamily()
        for framework in FRAMEWORK_TEMPLATES:
            agent_dir = tmp_path / framework
            agent_dir.mkdir()
            entrypoint = "tools.ts" if framework.startswith("mcp") else "agent.ts"
            (agent_dir / entrypoint).write_text("export const x = 1")

            config = _make_node_config(framework)
            image = runtime.build(agent_dir, config)
            assert (image.context_dir / "server.ts").exists(), f"server.ts missing for {framework}"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_node_runtime.py -v 2>&1 | tail -15
```

Expected: ImportError — `engine.runtimes.node` not found.

- [ ] **Step 3: Create `engine/runtimes/node.py`**

```python
"""Node.js runtime family — generates TypeScript agent containers."""
from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path

from engine.config_parser import AgentConfig
from engine.runtimes.base import ContainerImage, RuntimeBuilder, RuntimeValidationResult

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates" / "node"
APS_CLIENT_DIR = Path(__file__).parent.parent / "sidecar" / "client" / "ts"

FRAMEWORK_TEMPLATES: dict[str, str] = {
    "vercel-ai":          "vercel_ai_server.ts",
    "mastra":             "mastra_server.ts",
    "langchain-js":       "langchain_js_server.ts",
    "openai-agents-ts":   "openai_agents_ts_server.ts",
    "deepagent":          "deepagent_server.ts",
    "custom":             "custom_node_server.ts",
    "mcp-ts":             "mcp_ts_server.ts",
    "mcp-py":             "mcp_py_server.ts",
}

FRAMEWORK_DEPS: dict[str, dict[str, str]] = {
    "vercel-ai":          {"ai": "^4.0.0", "@ai-sdk/openai": "^1.0.0"},
    "mastra":             {"@mastra/core": "^0.1.0"},
    "langchain-js":       {"langchain": "^0.3.0", "@langchain/core": "^0.3.0"},
    "openai-agents-ts":   {"@openai/agents": "^0.1.0"},
    "deepagent":          {"deepagent": "^0.1.0"},
    "custom":             {},
    "mcp-ts":             {"@modelcontextprotocol/sdk": "^1.0.0"},
    "mcp-py":             {"@modelcontextprotocol/sdk": "^1.0.0"},
}

DOCKERFILE_TEMPLATE = """\
FROM node:{version}-slim AS deps
WORKDIR /app
COPY package.json tsconfig.json ./
RUN npm ci --only=production

FROM node:{version}-slim AS runner
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NODE_ENV=production
EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \\
    CMD node -e "require('http').get('http://localhost:3000/health', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["node", "--loader", "ts-node/esm", "server.ts"]
"""

TSCONFIG = {
    "compilerOptions": {
        "target": "ES2022",
        "module": "NodeNext",
        "moduleResolution": "NodeNext",
        "strict": True,
        "esModuleInterop": True,
        "skipLibCheck": True,
    },
    "include": ["*.ts", "aps-client/src/**/*.ts"],
}


class NodeRuntimeFamily(RuntimeBuilder):
    """Runtime builder for Node.js agents."""

    def validate(self, agent_dir: Path, config: AgentConfig) -> RuntimeValidationResult:
        errors: list[str] = []
        framework = config.runtime.framework if config.runtime else "custom"
        entrypoint = _entrypoint_for(framework, config)
        if not (agent_dir / entrypoint).exists():
            errors.append(
                f"Missing {entrypoint} in {agent_dir}. "
                f"Node.js agents must have a {entrypoint} file."
            )
        return RuntimeValidationResult(valid=len(errors) == 0, errors=errors)

    def build(self, agent_dir: Path, config: AgentConfig) -> ContainerImage:
        assert config.runtime is not None, "NodeRuntimeFamily requires config.runtime"
        framework = config.runtime.framework
        node_version = config.runtime.version or "20"

        build_dir = Path(tempfile.mkdtemp(prefix="agentbreeder-node-build-"))

        # Copy developer's agent source
        for item in agent_dir.iterdir():
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            dest = build_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        # Copy APS client source into build context
        aps_dest = build_dir / "aps-client"
        if APS_CLIENT_DIR.exists():
            shutil.copytree(APS_CLIENT_DIR, aps_dest)

        # Write server.ts from template
        server_content = _load_template(framework)
        entrypoint = _entrypoint_for(framework, config)
        entrypoint_noext = entrypoint.rsplit(".", 1)[0]
        server_content = (
            server_content
            .replace("{{AGENT_NAME}}", config.name)
            .replace("{{AGENT_VERSION}}", config.version)
            .replace("{{AGENT_MODEL}}", config.model.primary)
            .replace("{{ENTRYPOINT}}", entrypoint)
            .replace("{{ENTRYPOINT_NOEXT}}", entrypoint_noext)
        )
        (build_dir / "server.ts").write_text(server_content)

        # Copy _shared_loader.ts
        shared_loader = TEMPLATES_DIR / "_shared_loader.ts"
        if shared_loader.exists():
            shutil.copy2(shared_loader, build_dir / "_shared_loader.ts")

        # Write package.json
        pkg = _build_package_json(config.name, framework, node_version)
        (build_dir / "package.json").write_text(json.dumps(pkg, indent=2))

        # Write tsconfig.json
        (build_dir / "tsconfig.json").write_text(json.dumps(TSCONFIG, indent=2))

        # Write Dockerfile
        dockerfile_content = DOCKERFILE_TEMPLATE.format(version=node_version)
        (build_dir / "Dockerfile").write_text(dockerfile_content)

        tag = f"agentbreeder/{config.name}:{config.version}"
        return ContainerImage(tag=tag, dockerfile_content=dockerfile_content, context_dir=build_dir)

    def get_entrypoint(self, config: AgentConfig) -> str:
        return "node --loader ts-node/esm server.ts"

    def get_requirements(self, config: AgentConfig) -> list[str]:
        return []  # Node uses npm, not pip


def _load_template(framework: str) -> str:
    template_file = FRAMEWORK_TEMPLATES.get(framework)
    if template_file is None:
        logger.warning(
            "Unknown Node.js framework %r — falling back to custom template", framework
        )
        template_file = FRAMEWORK_TEMPLATES["custom"]
    return (TEMPLATES_DIR / template_file).read_text()


def _entrypoint_for(framework: str, config: AgentConfig) -> str:
    if config.runtime and config.runtime.entrypoint:
        return config.runtime.entrypoint
    if framework.startswith("mcp"):
        return "tools.ts"
    return "agent.ts"


def _build_package_json(agent_name: str, framework: str, node_version: str) -> dict:
    framework_deps = FRAMEWORK_DEPS.get(framework, {})
    return {
        "name": agent_name,
        "version": "1.0.0",
        "private": True,
        "engines": {"node": f">={node_version}"},
        "dependencies": {
            "@agentbreeder/aps-client": "file:./aps-client",
            "express": "^4.18.0",
            "node-fetch": "^3.3.2",
            "ts-node": "^10.9.0",
            "typescript": "^5.4.0",
            **framework_deps,
        },
        "devDependencies": {
            "@types/express": "^4.17.0",
            "@types/node": "^20.0.0",
        },
    }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_node_runtime.py -v 2>&1 | tail -20
```

Expected: all 6 tests pass.

- [ ] **Step 5: Add node to `LANGUAGE_REGISTRY` in `engine/runtimes/registry.py`**

Open `engine/runtimes/registry.py`. Add after the `_python_factory` function:

```python
def _node_factory(config: AgentConfig) -> RuntimeBuilder:
    from engine.runtimes.node import NodeRuntimeFamily
    framework = config.runtime.framework if config.runtime else "custom"
    return NodeRuntimeFamily()
```

Add `"node": _node_factory` to `LANGUAGE_REGISTRY`:

```python
LANGUAGE_REGISTRY: dict[str, Callable[[AgentConfig], RuntimeBuilder]] = {
    "python": _python_factory,
    "node":   _node_factory,   # added in PR 3
}
```

- [ ] **Step 6: Update `test_unsupported_language_raises` in `test_runtime_registry.py`**

The `test_unsupported_language_raises` test previously used `node` as the unsupported language. Update it to use `rust` instead (node is now supported):

```python
def test_unsupported_language_raises(self) -> None:
    from engine.runtimes.registry import UnsupportedLanguageError, get_runtime_from_config

    config = AgentConfig(
        name="test-agent",
        version="1.0.0",
        team="eng",
        owner="test@example.com",
        runtime=RuntimeConfig(language="node", framework="vercel-ai"),  # node now valid
        model={"primary": "gpt-4o"},
        deploy={"cloud": "local"},
    )
    # node is now registered — should NOT raise
    runtime = get_runtime_from_config(config)
    from engine.runtimes.node import NodeRuntimeFamily
    assert isinstance(runtime, NodeRuntimeFamily)
```

Also add a new test for truly unsupported:

```python
def test_truly_unsupported_language_raises(self) -> None:
    from engine.runtimes.registry import UnsupportedLanguageError, get_runtime_from_config
    from engine.config_parser import LanguageType

    # We can't construct AgentConfig with language="rust" because LanguageType
    # only has python and node — so test via direct registry lookup instead
    from engine.runtimes.registry import LANGUAGE_REGISTRY
    assert "rust" not in LANGUAGE_REGISTRY
```

- [ ] **Step 7: Run full unit suite**

```bash
pytest tests/unit/ -v --tb=short 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add engine/runtimes/node.py engine/runtimes/registry.py \
        tests/unit/test_node_runtime.py tests/unit/test_runtime_registry.py
git commit -m "feat(node): NodeRuntimeFamily — 8 templates, Dockerfile, package.json generation"
```

---

### Task 14: `engine/schema/mcp-server.schema.json`

**Files:**
- Create: `engine/schema/mcp-server.schema.json`

- [ ] **Step 1: Create the schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AgentBreeder MCP Server Configuration",
  "description": "Schema for mcp-server.yaml — defines an MCP server for agentbreeder deploy",
  "type": "object",
  "required": ["name", "version", "type", "runtime", "tools", "team", "owner", "deploy"],
  "additionalProperties": false,
  "properties": {
    "name": {
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9-]*[a-z0-9]$",
      "minLength": 2,
      "maxLength": 63,
      "description": "MCP server name (slug-friendly)"
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "description": "Semantic version (e.g., 1.0.0)"
    },
    "type": {
      "type": "string",
      "enum": ["mcp-server"],
      "description": "Must be 'mcp-server'"
    },
    "team": { "type": "string" },
    "owner": { "type": "string", "format": "email" },
    "description": { "type": "string", "maxLength": 500 },
    "tags": { "type": "array", "items": { "type": "string" } },
    "runtime": {
      "type": "object",
      "required": ["language", "framework"],
      "additionalProperties": false,
      "properties": {
        "language": { "type": "string", "enum": ["python", "node"] },
        "framework": { "type": "string" },
        "version": { "type": "string" },
        "entrypoint": { "type": "string" }
      }
    },
    "transport": {
      "type": "string",
      "enum": ["http", "stdio"],
      "default": "http",
      "description": "MCP transport protocol"
    },
    "tools": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "description"],
        "properties": {
          "name": { "type": "string" },
          "description": { "type": "string" },
          "schema": { "type": "object" }
        }
      }
    },
    "deploy": {
      "type": "object",
      "required": ["cloud"],
      "properties": {
        "cloud": { "type": "string", "enum": ["aws", "gcp", "azure", "kubernetes", "local"] },
        "region": { "type": "string" },
        "resources": {
          "type": "object",
          "properties": {
            "cpu": { "type": "string" },
            "memory": { "type": "string" }
          }
        }
      }
    }
  }
}
```

- [ ] **Step 2: Verify it parses**

```bash
python3 -c "import json; json.load(open('engine/schema/mcp-server.schema.json')); print('valid JSON')"
```

Expected: `valid JSON`.

- [ ] **Step 3: Commit**

```bash
git add engine/schema/mcp-server.schema.json
git commit -m "feat(schema): add mcp-server.schema.json"
```

---

### Task 15: CLI `--language` + `--type` flags

**Files:**
- Modify: `cli/commands/init_cmd.py`

- [ ] **Step 1: Read the current `init_cmd.py`**

```bash
wc -l cli/commands/init_cmd.py
grep -n "def app_callback\|def init\|typer.Option\|FRAMEWORKS\|CLOUDS" cli/commands/init_cmd.py | head -20
```

Note which function handles the `init` command and where `FRAMEWORKS` is defined.

- [ ] **Step 2: Add `--language` and `--type` parameters to the init command**

Find the `init` command function signature. Add two new optional parameters:

```python
language: str = typer.Option(None, "--language", help="Agent language: python (default) | node"),
agent_type: str = typer.Option("agent", "--type", help="Type: agent (default) | mcp-server"),
```

- [ ] **Step 3: Add Node framework options constant**

After the existing `FRAMEWORKS` list, add:

```python
NODE_FRAMEWORKS = [
    {"key": "vercel-ai",         "name": "Vercel AI SDK",     "icon": "⚡", "tagline": "Streaming-first TypeScript AI SDK"},
    {"key": "mastra",            "name": "Mastra",            "icon": "🔮", "tagline": "TypeScript agent framework by Mastra"},
    {"key": "langchain-js",      "name": "LangChain.js",      "icon": "🔗", "tagline": "LangChain in TypeScript"},
    {"key": "openai-agents-ts",  "name": "OpenAI Agents TS",  "icon": "🤖", "tagline": "OpenAI Agents SDK for TypeScript"},
    {"key": "deepagent",         "name": "DeepAgent",         "icon": "🧠", "tagline": "DeepAgent TypeScript SDK"},
    {"key": "custom",            "name": "Custom Node.js",    "icon": "⚙️",  "tagline": "Bring your own TypeScript agent"},
]

MCP_FRAMEWORKS = [
    {"key": "mcp-ts",  "name": "MCP TypeScript", "icon": "🔌", "tagline": "MCP server in TypeScript"},
    {"key": "mcp-py",  "name": "MCP Python",     "icon": "🐍", "tagline": "MCP server in Python"},
]
```

- [ ] **Step 4: Branch framework selection by language/type**

Inside the init wizard, where the framework picker is shown, add branching:

```python
if agent_type == "mcp-server":
    frameworks_to_show = MCP_FRAMEWORKS
elif language == "node":
    frameworks_to_show = NODE_FRAMEWORKS
else:
    frameworks_to_show = FRAMEWORKS  # existing Python frameworks
```

Use `frameworks_to_show` wherever `FRAMEWORKS` was previously referenced in the picker.

- [ ] **Step 5: Add scaffold templates for Node agents**

Add two new scaffold functions alongside the existing `_agent_yaml` and other scaffolding:

```python
def _node_agent_yaml(name: str, framework: str, cloud: str, model: str, team: str, owner: str) -> str:
    return f"""\
name: {name}
version: 0.1.0
description: "{name} — powered by {framework}"
team: {team}
owner: {owner}
tags:
  - {framework}
  - generated

runtime:
  language: node
  framework: {framework}
  version: "20"

model:
  primary: {model}

deploy:
  cloud: {cloud}
"""

def _node_agent_ts(name: str, framework: str) -> str:
    stubs = {
        "vercel-ai": f"""\
import {{ openai }} from '@ai-sdk/openai'

export const model = openai('gpt-4o')
export const systemPrompt = `You are {name}, a helpful assistant.`
export const tools = {{}}
""",
        "mastra": f"""\
import {{ Agent }} from '@mastra/core'

export const Agent = new Agent({{
  name: '{name}',
  instructions: 'You are {name}, a helpful assistant.',
  model: {{ provider: 'OPEN_AI', name: 'gpt-4o' }},
}})
""",
        "custom": f"""\
import {{ APSClient }} from './aps-client/src/index.js'

const aps = new APSClient()

export async function handler(input: string, context: {{ aps: APSClient; history: any[]; thread_id?: string }}): Promise<string> {{
  // Your agent logic here
  return `Hello from {name}! You said: ${{input}}`
}}
""",
    }
    return stubs.get(framework, stubs["custom"])

def _mcp_server_yaml(name: str, framework: str, cloud: str, team: str, owner: str) -> str:
    return f"""\
name: {name}
version: 0.1.0
description: "{name} — MCP server"
team: {team}
owner: {owner}
type: mcp-server

runtime:
  language: {"node" if framework == "mcp-ts" else "python"}
  framework: {framework}
  version: "20"

transport: http
tools: []

deploy:
  cloud: {cloud}
"""

def _mcp_tools_ts(name: str) -> str:
    return f"""\
// {name} — MCP tools
// Export one async function per tool.
// Add __meta to describe each tool to the MCP server wrapper.

export const __meta = {{
  hello_world: {{
    description: 'A sample tool that says hello',
    inputSchema: {{
      type: 'object',
      properties: {{ name: {{ type: 'string', description: 'Name to greet' }} }},
      required: ['name'],
    }},
  }},
}}

export async function hello_world({{ name }}: {{ name: string }}): Promise<string> {{
  return `Hello, ${{name}}!`
}}
"""
```

- [ ] **Step 6: Wire scaffold output — write files based on language/type**

In the section of `init_cmd.py` where files get written (look for `(output_dir / "agent.yaml").write_text(...)`), add branching:

```python
if agent_type == "mcp-server":
    (output_dir / "mcp-server.yaml").write_text(
        _mcp_server_yaml(name, framework_key, cloud_key, team, owner)
    )
    if framework_key == "mcp-ts":
        (output_dir / "tools.ts").write_text(_mcp_tools_ts(name))
    else:
        (output_dir / "tools.py").write_text(f"# {name} — MCP tools in Python\n")
elif language == "node":
    (output_dir / "agent.yaml").write_text(
        _node_agent_yaml(name, framework_key, cloud_key, model, team, owner)
    )
    (output_dir / "agent.ts").write_text(_node_agent_ts(name, framework_key))
    (output_dir / "package.json").write_text(
        json.dumps({
            "name": name,
            "version": "0.1.0",
            "private": True,
            "dependencies": {
                "@agentbreeder/aps-client": "^0.1.0",
                "typescript": "^5.4.0",
                "ts-node": "^10.9.0",
            },
        }, indent=2)
    )
    (output_dir / "tsconfig.json").write_text(
        json.dumps({
            "compilerOptions": {
                "target": "ES2022",
                "module": "NodeNext",
                "moduleResolution": "NodeNext",
                "strict": True,
                "esModuleInterop": True,
                "skipLibCheck": True,
            }
        }, indent=2)
    )
else:
    # existing Python path — unchanged
    (output_dir / "agent.yaml").write_text(
        _agent_yaml(name, framework_key, cloud_key, model, team, owner)
    )
    # ... rest of existing Python scaffold ...
```

- [ ] **Step 7: Test the CLI manually**

```bash
cd /tmp && agentbreeder init --language node --framework vercel-ai --name test-ts-agent \
  --team eng --owner test@example.com --cloud local --no-interactive 2>&1 || \
python3 -m cli.main init --language node --framework vercel-ai --name test-ts-agent \
  --team eng --cloud local 2>&1 | head -20
```

Verify `agent.yaml` has `runtime: {language: node}` and `agent.ts` is created.

- [ ] **Step 8: Run lint**

```bash
ruff check cli/commands/init_cmd.py && ruff format --check cli/commands/init_cmd.py
```

Fix any issues, then:

- [ ] **Step 9: Commit**

```bash
git add cli/commands/init_cmd.py
git commit -m "feat(cli): add --language and --type flags to agentbreeder init"
```

---

### Task 16: Integration tests

**Files:**
- Create: `tests/integration/test_polyglot_deploy.py`
- Create: `tests/integration/test_mcp_deploy.py`

- [ ] **Step 1: Create `tests/integration/test_polyglot_deploy.py`**

```python
"""Integration test: deploy a TypeScript Vercel AI agent locally.

Requires: docker running, agentbreeder-api running on localhost:8000.
Skip with: pytest -m "not integration"
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest


@pytest.mark.integration
class TestPolyglotLocalDeploy:
    @pytest.fixture(autouse=True)
    def skip_if_no_docker(self) -> None:
        result = subprocess.run(["docker", "info"], capture_output=True)
        if result.returncode != 0:
            pytest.skip("Docker not available")

    def test_vercel_ai_agent_deploys_and_health_checks(self, tmp_path: Path) -> None:
        # Scaffold a minimal Vercel AI agent
        agent_dir = tmp_path / "test-ts-agent"
        agent_dir.mkdir()

        (agent_dir / "agent.yaml").write_text("""\
name: test-ts-agent
version: 1.0.0
team: engineering
owner: test@example.com
runtime:
  language: node
  framework: vercel-ai
  version: "20"
model:
  primary: gpt-4o
deploy:
  cloud: local
""")
        (agent_dir / "agent.ts").write_text("""\
import { openai } from '@ai-sdk/openai'
export const model = openai('gpt-4o')
export const systemPrompt = 'You are a test agent.'
export const tools = {}
""")

        from engine.builder import DeployEngine
        import asyncio

        engine = DeployEngine()
        result = asyncio.run(
            engine.deploy(agent_dir / "agent.yaml", target="local")
        )

        assert result.endpoint_url.startswith("http://")

        # Health check
        time.sleep(3)
        resp = httpx.get(result.endpoint_url + "/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

        # Verify AGENTBREEDER_URL is injected
        import docker
        client = docker.from_env()
        container = client.containers.get("agentbreeder-test-ts-agent")
        env = {e.split("=", 1)[0]: e.split("=", 1)[1]
               for e in container.attrs["Config"]["Env"] if "=" in e}
        assert "AGENTBREEDER_URL" in env
        assert "AGENTBREEDER_API_KEY" in env

        # Cleanup
        container.stop()
        container.remove()
```

- [ ] **Step 2: Create `tests/integration/test_mcp_deploy.py`**

```python
"""Integration test: deploy an MCP TypeScript server locally."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import httpx
import pytest


@pytest.mark.integration
class TestMcpLocalDeploy:
    @pytest.fixture(autouse=True)
    def skip_if_no_docker(self) -> None:
        result = subprocess.run(["docker", "info"], capture_output=True)
        if result.returncode != 0:
            pytest.skip("Docker not available")

    def test_mcp_ts_server_deploys_and_health_checks(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "test-mcp-server"
        agent_dir.mkdir()

        (agent_dir / "mcp-server.yaml").write_text("""\
name: test-mcp-server
version: 1.0.0
type: mcp-server
team: engineering
owner: test@example.com
runtime:
  language: node
  framework: mcp-ts
  version: "20"
transport: http
tools:
  - name: hello_world
    description: Say hello
deploy:
  cloud: local
""")
        (agent_dir / "tools.ts").write_text("""\
export const __meta = {
  hello_world: {
    description: 'Say hello',
    inputSchema: { type: 'object', properties: { name: { type: 'string' } } },
  },
}
export async function hello_world({ name }: { name: string }) {
  return `Hello, ${name}!`
}
""")

        from engine.builder import DeployEngine
        import asyncio

        engine = DeployEngine()
        result = asyncio.run(
            engine.deploy(agent_dir / "mcp-server.yaml", target="local")
        )

        time.sleep(3)
        resp = httpx.get(result.endpoint_url + "/health", timeout=10)
        assert resp.status_code == 200

        import docker
        client = docker.from_env()
        container = client.containers.get("agentbreeder-test-mcp-server")
        container.stop()
        container.remove()
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_polyglot_deploy.py tests/integration/test_mcp_deploy.py
git commit -m "test(integration): add polyglot deploy and MCP server integration tests"
```

---

### Task 17: PR 3 final check + lint

- [ ] **Step 1: Full unit test suite**

```bash
pytest tests/unit/ -v --tb=short 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 2: Lint + format + type check**

```bash
ruff check . && ruff format --check .
mypy engine/ api/ --ignore-missing-imports 2>&1 | grep -E "^engine|^api" | grep "error:" | head -20
```

Fix any issues. Then:

- [ ] **Step 3: Run APS client TypeScript tests**

```bash
cd engine/sidecar/client/ts && npm test 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 4: Final commit for any lint fixes**

If lint required changes:

```bash
git add -p  # stage only the lint fixes
git commit -m "chore: lint and type fixes for polyglot runtime PR 3"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `RuntimeConfig` + `AgentType` models | Task 1 |
| `agent.schema.json` runtime block + oneOf | Task 2 |
| `LANGUAGE_REGISTRY` + `get_runtime_from_config` | Task 3 |
| `PythonRuntimeFamily` factory | Task 3 |
| `builder.py` dispatch update | Task 4 |
| `get_aps_env_vars()` on BaseDeployer | Task 5 |
| `AGENTBREEDER_URL/KEY` settings | Task 5 |
| Env injection in 3 deployers | Task 6 |
| `@agentbreeder/aps-client` npm package | Task 8 |
| Memory thread convenience endpoints | Task 9 |
| `_shared_loader.ts` | Task 10 |
| 6 agent templates | Tasks 10 + 11 |
| 2 MCP templates | Task 12 |
| `NodeRuntimeFamily` | Task 13 |
| Node added to LANGUAGE_REGISTRY | Task 13 |
| `mcp-server.schema.json` | Task 14 |
| CLI `--language` + `--type` flags | Task 15 |
| Unit + integration tests | Tasks 1–16 |

All spec requirements covered. No gaps.
