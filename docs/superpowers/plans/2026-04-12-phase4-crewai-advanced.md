# Phase 4: CrewAI Advanced Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CrewAI Flows support, hierarchical/parallel process, crewai-tools dependency, `crewai:` YAML schema block, and Pydantic structured outputs to the CrewAI runtime.

**Architecture:** `AgentConfig` gains an optional `crewai: CrewAIConfig` sub-config read from `agent.yaml`. The server template detects `flow` vs `crew` at startup and dispatches accordingly. The runtime builder reads `crewai.process` and `crewai.manager_llm` to configure the Crew. `agent.schema.json` gets a `crewai:` block for YAML validation.

**Tech Stack:** crewai 0.80+, `crewai.flow.flow.Flow`, `crewai.Process`, `crewai.LLM`, crewai-tools, pydantic

**Files touched:**
- `engine/config_parser.py` — add `CrewAIConfig` Pydantic model, add `crewai` field to `AgentConfig`
- `engine/schema/agent.schema.json` — add `crewai` property block
- `engine/runtimes/crewai.py` — add `crewai-tools` to requirements, read `crewai.process` + `crewai.manager_llm`, forward as `AGENT_CREWAI_PROCESS` / `AGENT_CREWAI_MANAGER_LLM` / `AGENT_CREWAI_VERBOSE` / `AGENT_CREWAI_MEMORY` ENV directives
- `engine/runtimes/templates/crewai_server.py` — detect flow vs crew at startup, async flow dispatch, structured output validation
- `tests/unit/test_crewai_advanced.py` — new test file covering all four feature areas

**Test file:** `tests/unit/test_crewai_advanced.py`

---

## Task 1: Add `CrewAIConfig` to `engine/config_parser.py` + update JSON schema

**What:** Introduce a `CrewAIConfig` Pydantic model with `process`, `manager_llm`, `verbose`, `memory`, and `memory_config` fields. Add an optional `crewai: CrewAIConfig | None = None` field to `AgentConfig`. Add the matching `crewai` block to `engine/schema/agent.schema.json` so `agentbreeder validate` accepts the new fields.

### Step 1.1 — Write the failing tests

- [ ] Create `tests/unit/test_crewai_advanced.py` with the following test class:

```python
"""Tests for Phase 4 CrewAI advanced features."""
import json
from pathlib import Path

import pytest

from engine.config_parser import (
    AgentConfig,
    CrewAIConfig,
    FrameworkType,
    parse_config,
    validate_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides: object) -> AgentConfig:
    defaults: dict = {
        "name": "test-agent",
        "version": "1.0.0",
        "team": "eng",
        "owner": "dev@example.com",
        "framework": FrameworkType.crewai,
        "model": {"primary": "claude-sonnet-4"},
        "deploy": {"cloud": "local"},
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)


# ---------------------------------------------------------------------------
# Task 1: CrewAIConfig Pydantic model
# ---------------------------------------------------------------------------

class TestCrewAIConfig:
    def test_crewai_config_defaults(self) -> None:
        cfg = CrewAIConfig()
        assert cfg.process == "sequential"
        assert cfg.manager_llm is None
        assert cfg.verbose is False
        assert cfg.memory is False
        assert cfg.memory_config is None

    def test_crewai_config_hierarchical(self) -> None:
        cfg = CrewAIConfig(process="hierarchical", manager_llm="claude-opus-4", verbose=True)
        assert cfg.process == "hierarchical"
        assert cfg.manager_llm == "claude-opus-4"
        assert cfg.verbose is True

    def test_crewai_config_parallel(self) -> None:
        cfg = CrewAIConfig(process="parallel")
        assert cfg.process == "parallel"

    def test_crewai_config_rejects_unknown_process(self) -> None:
        with pytest.raises(Exception):
            CrewAIConfig(process="unknown-mode")

    def test_crewai_config_memory_config_dict(self) -> None:
        cfg = CrewAIConfig(memory=True, memory_config={"provider": "mem0", "config": {"user_id": "u1"}})
        assert cfg.memory is True
        assert cfg.memory_config["provider"] == "mem0"

    def test_agent_config_crewai_field_defaults_none(self) -> None:
        cfg = _make_config()
        assert cfg.crewai is None

    def test_agent_config_crewai_field_accepts_config(self) -> None:
        cfg = _make_config(crewai={"process": "hierarchical", "manager_llm": "claude-opus-4"})
        assert cfg.crewai is not None
        assert cfg.crewai.process == "hierarchical"
        assert cfg.crewai.manager_llm == "claude-opus-4"

    def test_agent_config_crewai_field_coerces_from_dict(self) -> None:
        cfg = _make_config(crewai={"process": "parallel", "verbose": True})
        assert isinstance(cfg.crewai, CrewAIConfig)
        assert cfg.crewai.process == "parallel"
        assert cfg.crewai.verbose is True


class TestAgentSchemaCrewAIBlock:
    """Validate that the JSON schema accepts/rejects crewai: blocks."""

    _SCHEMA_PATH = Path("engine/schema/agent.schema.json")
    _VALID_BASE = Path("tests/unit/fixtures/crewai_schema_valid.yaml")
    _INVALID_PROCESS = Path("tests/unit/fixtures/crewai_schema_invalid_process.yaml")

    def test_schema_accepts_hierarchical_crewai_block(self, tmp_path: Path) -> None:
        yaml_content = """\
name: hier-agent
version: 1.0.0
team: eng
owner: dev@example.com
framework: crewai
model:
  primary: claude-sonnet-4
deploy:
  cloud: local
crewai:
  process: hierarchical
  manager_llm: claude-opus-4
  verbose: true
  memory: true
"""
        p = tmp_path / "agent.yaml"
        p.write_text(yaml_content)
        result = validate_config(p)
        assert result.valid, result.errors

    def test_schema_accepts_parallel_crewai_block(self, tmp_path: Path) -> None:
        yaml_content = """\
name: par-agent
version: 1.0.0
team: eng
owner: dev@example.com
framework: crewai
model:
  primary: claude-sonnet-4
deploy:
  cloud: local
crewai:
  process: parallel
  verbose: false
"""
        p = tmp_path / "agent.yaml"
        p.write_text(yaml_content)
        result = validate_config(p)
        assert result.valid, result.errors

    def test_schema_rejects_invalid_process_value(self, tmp_path: Path) -> None:
        yaml_content = """\
name: bad-agent
version: 1.0.0
team: eng
owner: dev@example.com
framework: crewai
model:
  primary: claude-sonnet-4
deploy:
  cloud: local
crewai:
  process: turbo
"""
        p = tmp_path / "agent.yaml"
        p.write_text(yaml_content)
        result = validate_config(p)
        assert not result.valid
        assert any("process" in str(e.message).lower() for e in result.errors)
```

### Step 1.2 — Confirm tests fail

- [ ] Run:
```bash
pytest tests/unit/test_crewai_advanced.py::TestCrewAIConfig tests/unit/test_crewai_advanced.py::TestAgentSchemaCrewAIBlock -v 2>&1 | head -40
```
Expected: `ImportError: cannot import name 'CrewAIConfig'` and schema tests fail on missing `crewai` property.

### Step 1.3 — Implement `CrewAIConfig` in `engine/config_parser.py`

- [ ] After the existing `GuardrailConfig` class (line ~119) and before `AgentConfig` (line ~122), insert:

```python
class CrewAIConfig(BaseModel):
    """Optional CrewAI-specific configuration block."""

    process: str = Field(
        default="sequential",
        description="Crew execution process. One of: sequential, hierarchical, parallel.",
    )
    manager_llm: str | None = Field(
        default=None,
        description="Model ref for the manager agent. Required when process=hierarchical.",
    )
    verbose: bool = False
    memory: bool = False
    memory_config: dict[str, Any] | None = None

    @field_validator("process")
    @classmethod
    def validate_process(cls, v: str) -> str:
        allowed = {"sequential", "hierarchical", "parallel"}
        if v not in allowed:
            raise ValueError(f"crewai.process must be one of {sorted(allowed)}, got {v!r}")
        return v
```

- [ ] In the `AgentConfig` class, add the field after `guardrails`:

```python
    crewai: CrewAIConfig | None = None
```

- [ ] In `engine/config_parser.py`, update the `__all__` export list (or the imports used in tests) to include `CrewAIConfig`.

### Step 1.4 — Add `crewai` block to `engine/schema/agent.schema.json`

- [ ] Locate the top-level `"properties"` object (line 8). Add a `"crewai"` entry alongside the existing properties (e.g., after `"guardrails"`):

```json
"crewai": {
  "type": "object",
  "description": "CrewAI-specific configuration. Only relevant when framework is crewai.",
  "properties": {
    "process": {
      "type": "string",
      "enum": ["sequential", "hierarchical", "parallel"],
      "default": "sequential",
      "description": "Crew execution process type."
    },
    "manager_llm": {
      "type": "string",
      "description": "Model ref for the manager agent. Required when process=hierarchical."
    },
    "verbose": {
      "type": "boolean",
      "default": false
    },
    "memory": {
      "type": "boolean",
      "default": false
    },
    "memory_config": {
      "type": "object",
      "description": "Advanced memory provider config passed directly to Crew(memory_config=...).",
      "additionalProperties": true
    }
  },
  "additionalProperties": false
}
```

### Step 1.5 — Confirm tests pass

- [ ] Run:
```bash
pytest tests/unit/test_crewai_advanced.py::TestCrewAIConfig tests/unit/test_crewai_advanced.py::TestAgentSchemaCrewAIBlock -v
```
Expected: all 11 tests green.

Also confirm existing config parser tests still pass:
```bash
pytest tests/unit/test_config_parser.py -v
```

### Step 1.6 — Commit

- [ ] Commit with message:
```
feat(config): add CrewAIConfig sub-model and crewai: JSON schema block

AgentConfig gains an optional `crewai: CrewAIConfig` field supporting
process (sequential/hierarchical/parallel), manager_llm, verbose, memory,
and memory_config. agent.schema.json validates the new block.
```

---

## Task 2: Add `crewai-tools` to requirements + pass `process` and `manager_llm` in `crewai.py`

**What:** `CrewAIRuntime.get_requirements()` must include `crewai-tools>=0.4.0`. `CrewAIRuntime.build()` must emit `AGENT_CREWAI_PROCESS`, `AGENT_CREWAI_MANAGER_LLM`, `AGENT_CREWAI_VERBOSE`, and `AGENT_CREWAI_MEMORY` as Dockerfile `ENV` directives when a `crewai:` block is present, so the server template can read them at runtime.

### Step 2.1 — Write the failing tests

- [ ] Append to `tests/unit/test_crewai_advanced.py`:

```python
import tempfile
from engine.runtimes.crewai import CrewAIRuntime


# ---------------------------------------------------------------------------
# Task 2: crewai-tools in requirements + process/manager_llm ENV vars
# ---------------------------------------------------------------------------

class TestCrewAIRuntimeAdvancedRequirements:
    def test_get_requirements_includes_crewai_tools(self) -> None:
        rt = CrewAIRuntime()
        reqs = rt.get_requirements(_make_config())
        assert any("crewai-tools" in r for r in reqs), f"crewai-tools missing from {reqs}"

    def test_crewai_tools_version_pinned_gte_0_4(self) -> None:
        rt = CrewAIRuntime()
        reqs = rt.get_requirements(_make_config())
        tools_req = next(r for r in reqs if "crewai-tools" in r)
        assert ">=" in tools_req, f"Expected pinned version constraint, got {tools_req!r}"


class TestCrewAIRuntimeBuildEnvVars:
    def _build_and_read_dockerfile(self, crewai_cfg: dict | None) -> str:
        rt = CrewAIRuntime()
        config = _make_config(crewai=crewai_cfg)
        with tempfile.TemporaryDirectory() as d:
            agent_dir = Path(d)
            (agent_dir / "crew.py").write_text("crew = None\n")
            (agent_dir / "requirements.txt").write_text("crewai\n")
            image = rt.build(agent_dir, config)
            dockerfile = (image.context_dir / "Dockerfile").read_text()
        return dockerfile

    def test_build_no_crewai_block_omits_process_env(self) -> None:
        dockerfile = self._build_and_read_dockerfile(None)
        assert "AGENT_CREWAI_PROCESS" not in dockerfile

    def test_build_sequential_process_written_as_env(self) -> None:
        dockerfile = self._build_and_read_dockerfile({"process": "sequential"})
        assert "ENV AGENT_CREWAI_PROCESS=sequential" in dockerfile

    def test_build_hierarchical_process_written_as_env(self) -> None:
        dockerfile = self._build_and_read_dockerfile(
            {"process": "hierarchical", "manager_llm": "claude-opus-4"}
        )
        assert "ENV AGENT_CREWAI_PROCESS=hierarchical" in dockerfile
        assert "ENV AGENT_CREWAI_MANAGER_LLM=claude-opus-4" in dockerfile

    def test_build_parallel_process_written_as_env(self) -> None:
        dockerfile = self._build_and_read_dockerfile({"process": "parallel"})
        assert "ENV AGENT_CREWAI_PROCESS=parallel" in dockerfile

    def test_build_verbose_true_written_as_env(self) -> None:
        dockerfile = self._build_and_read_dockerfile({"verbose": True})
        assert "ENV AGENT_CREWAI_VERBOSE=true" in dockerfile

    def test_build_memory_true_written_as_env(self) -> None:
        dockerfile = self._build_and_read_dockerfile({"memory": True})
        assert "ENV AGENT_CREWAI_MEMORY=true" in dockerfile

    def test_build_manager_llm_absent_when_not_set(self) -> None:
        dockerfile = self._build_and_read_dockerfile({"process": "sequential"})
        assert "AGENT_CREWAI_MANAGER_LLM" not in dockerfile
```

### Step 2.2 — Confirm tests fail

- [ ] Run:
```bash
pytest tests/unit/test_crewai_advanced.py::TestCrewAIRuntimeAdvancedRequirements tests/unit/test_crewai_advanced.py::TestCrewAIRuntimeBuildEnvVars -v 2>&1 | head -40
```
Expected: `test_get_requirements_includes_crewai_tools` fails (not in list), all ENV var tests fail (no `AGENT_CREWAI_*` lines in Dockerfile).

### Step 2.3 — Implement in `engine/runtimes/crewai.py`

- [ ] In `get_requirements()` (lines 114–121), add `"crewai-tools>=0.4.0"` to the returned list. The method currently returns a list like `["crewai>=0.80.0", "fastapi", "uvicorn[standard]", ...]`. The updated return should be:

```python
    def get_requirements(self, config: AgentConfig) -> list[str]:
        return [
            "crewai>=0.80.0",
            "crewai-tools>=0.4.0",
            "fastapi>=0.111.0",
            "uvicorn[standard]>=0.29.0",
            "pydantic>=2.7.0",
        ]
```

- [ ] In `build()` (lines 70–109), after the existing ENV block that writes `AGENT_NAME`, `AGENT_VERSION`, etc., add a helper that emits CrewAI-specific ENV directives when `config.crewai` is set. Insert after the existing env block construction (look for where `AGENT_MODEL` / `AGENT_FRAMEWORK` lines are built) and before the `RUN pip install` line:

```python
        # CrewAI-specific ENV directives
        crewai_env_lines: list[str] = []
        if config.crewai is not None:
            crewai_env_lines.append(
                f"ENV AGENT_CREWAI_PROCESS={config.crewai.process}"
            )
            if config.crewai.manager_llm:
                crewai_env_lines.append(
                    f"ENV AGENT_CREWAI_MANAGER_LLM={config.crewai.manager_llm}"
                )
            if config.crewai.verbose:
                crewai_env_lines.append("ENV AGENT_CREWAI_VERBOSE=true")
            if config.crewai.memory:
                crewai_env_lines.append("ENV AGENT_CREWAI_MEMORY=true")
        crewai_env_block = "\n".join(crewai_env_lines)
```

Then interpolate `crewai_env_block` into the Dockerfile template string, e.g.:

```dockerfile
{crewai_env_block}
```

placed after the standard env block and before `COPY requirements.txt .`.

### Step 2.4 — Confirm tests pass

- [ ] Run:
```bash
pytest tests/unit/test_crewai_advanced.py::TestCrewAIRuntimeAdvancedRequirements tests/unit/test_crewai_advanced.py::TestCrewAIRuntimeBuildEnvVars -v
```
Expected: all 9 tests green.

Also confirm existing runtime tests are unbroken:
```bash
pytest tests/unit/test_runtime_crewai.py -v
```

### Step 2.5 — Commit

- [ ] Commit with message:
```
feat(crewai-runtime): add crewai-tools dep + emit AGENT_CREWAI_* ENV directives

get_requirements() now includes crewai-tools>=0.4.0. build() emits
AGENT_CREWAI_PROCESS, AGENT_CREWAI_MANAGER_LLM, AGENT_CREWAI_VERBOSE,
and AGENT_CREWAI_MEMORY Dockerfile ENV lines when a crewai: block is set.
```

---

## Task 3: Add Flow detection + `kickoff_async` dispatch to `crewai_server.py`

**What:** The server template currently assumes the agent module always exposes a `crew` variable. CrewAI 0.80+ agents may instead expose a `flow` variable (a `Flow` subclass instance). The startup logic must detect which mode is active and store both the object and the mode. The `/invoke` handler must dispatch to `flow.kickoff_async()` for flows and `crew.kickoff()` (in a thread) for crews. The `/health` endpoint must reflect the mode.

### Step 3.1 — Write the failing tests

- [ ] Append to `tests/unit/test_crewai_advanced.py`:

```python
import asyncio
import importlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Task 3: Flow detection + dispatch in crewai_server.py
# ---------------------------------------------------------------------------

def _make_crew_module(has_flow: bool = False, has_crew: bool = True) -> types.ModuleType:
    """Return a fake agent module with either a flow or a crew attribute."""
    mod = types.ModuleType("agent")
    if has_flow:
        flow_instance = MagicMock()
        flow_instance.kickoff_async = AsyncMock(return_value="flow-result")
        mod.flow = flow_instance
    if has_crew:
        crew_instance = MagicMock()
        crew_instance.kickoff = MagicMock(return_value="crew-result")
        mod.crew = crew_instance
    return mod


class TestCrewAIServerFlowDetection:
    """Unit tests for flow vs crew startup detection logic.

    We test the detection function directly rather than importing the full
    server module, to avoid FastAPI app-level side effects.
    """

    def test_detect_mode_returns_flow_when_flow_attribute_present(self) -> None:
        mod = _make_crew_module(has_flow=True, has_crew=False)
        mode, obj = _detect_mode(mod)
        assert mode == "flow"
        assert obj is mod.flow

    def test_detect_mode_returns_crew_when_only_crew_present(self) -> None:
        mod = _make_crew_module(has_flow=False, has_crew=True)
        mode, obj = _detect_mode(mod)
        assert mode == "crew"
        assert obj is mod.crew

    def test_detect_mode_prefers_flow_over_crew_when_both_present(self) -> None:
        mod = _make_crew_module(has_flow=True, has_crew=True)
        mode, obj = _detect_mode(mod)
        assert mode == "flow"

    def test_detect_mode_raises_when_neither_present(self) -> None:
        mod = types.ModuleType("agent")
        with pytest.raises(RuntimeError, match="neither 'flow' nor 'crew'"):
            _detect_mode(mod)


class TestCrewAIServerFlowDispatch:
    def test_flow_invoke_calls_kickoff_async(self) -> None:
        mod = _make_crew_module(has_flow=True, has_crew=False)
        result = asyncio.get_event_loop().run_until_complete(
            _dispatch(mod.flow, "flow", {"prompt": "hello"})
        )
        mod.flow.kickoff_async.assert_called_once_with(inputs={"prompt": "hello"})
        assert result == "flow-result"

    def test_crew_invoke_calls_kickoff_in_thread(self) -> None:
        mod = _make_crew_module(has_flow=False, has_crew=True)
        result = asyncio.get_event_loop().run_until_complete(
            _dispatch(mod.crew, "crew", {"prompt": "hello"})
        )
        mod.crew.kickoff.assert_called_once()
        assert result == "crew-result"


# Helper import shim — the test file imports these from the server template
# module so the plan stays honest about what functions must be exposed.
def _detect_mode(mod: types.ModuleType) -> tuple[str, object]:
    """Import and call crewai_server._detect_mode for testing."""
    # We import the function directly; the server module must export it.
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "crewai_server",
        pathlib.Path("engine/runtimes/templates/crewai_server.py"),
    )
    srv = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(srv)  # type: ignore[union-attr]
    return srv._detect_mode(mod)


async def _dispatch(obj: object, mode: str, input_data: dict) -> str:
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "crewai_server",
        pathlib.Path("engine/runtimes/templates/crewai_server.py"),
    )
    srv = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(srv)  # type: ignore[union-attr]
    return await srv._dispatch(obj, mode, input_data)
```

### Step 3.2 — Confirm tests fail

- [ ] Run:
```bash
pytest tests/unit/test_crewai_advanced.py::TestCrewAIServerFlowDetection tests/unit/test_crewai_advanced.py::TestCrewAIServerFlowDispatch -v 2>&1 | head -40
```
Expected: `AttributeError: module 'crewai_server' has no attribute '_detect_mode'` for all detection tests, dispatch tests fail because `_dispatch` does not exist.

### Step 3.3 — Implement in `engine/runtimes/templates/crewai_server.py`

Replace the current `_load_agent()` function and the module-level startup with a new detection architecture. The full replacement for `crewai_server.py`:

```python
"""AgentBreeder server wrapper for CrewAI agents.

Supports both classic Crew-based agents and CrewAI 0.80+ Flow-based agents.
Detection at startup: if the agent module exposes a `flow` attribute it is
treated as a Flow; otherwise a `crew` attribute is expected.
"""

import asyncio
import importlib
import logging
import os
import sys
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("crewai_server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AgentBreeder CrewAI Server")

# Module-level state populated at startup
_mode: str = "crew"       # "crew" | "flow"
_agent_obj: Any = None    # The crew or flow instance


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class InvokeRequest(BaseModel):
    input: str
    config: dict[str, Any] = {}


class InvokeResponse(BaseModel):
    output: str
    mode: str = "crew"   # echoed so callers know which path ran


class HealthResponse(BaseModel):
    status: str
    framework: str
    mode: str


# ---------------------------------------------------------------------------
# Detection and dispatch helpers (module-level so tests can import them)
# ---------------------------------------------------------------------------

def _detect_mode(agent_module: Any) -> tuple[str, Any]:
    """Return (mode, object) for the agent module.

    Prefers `flow` over `crew` when both are present.
    Raises RuntimeError if neither attribute is found.
    """
    if hasattr(agent_module, "flow"):
        return "flow", agent_module.flow
    if hasattr(agent_module, "crew"):
        return "crew", agent_module.crew
    raise RuntimeError(
        "Agent module exposes neither 'flow' nor 'crew' attribute. "
        "Define one of: flow = MyFlow(), crew = Crew(...)"
    )


async def _dispatch(obj: Any, mode: str, input_data: dict[str, Any]) -> str:
    """Dispatch an invocation to either a Flow or a Crew."""
    if mode == "flow":
        result = await obj.kickoff_async(inputs=input_data)
        return str(result)
    # Crew.kickoff is synchronous — run in thread pool to avoid blocking the loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: obj.kickoff(inputs=input_data))
    return str(result)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def _load_agent() -> None:
    """Dynamically load the agent module and detect flow vs crew mode."""
    global _mode, _agent_obj

    agent_dir = os.environ.get("AGENT_DIR", "/app")
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)

    # Try agent.py first, then crew.py (legacy)
    for module_name in ("agent", "crew"):
        try:
            mod = importlib.import_module(module_name)
            _mode, _agent_obj = _detect_mode(mod)
            logger.info("Loaded agent module %r in %s mode", module_name, _mode)
            return
        except ModuleNotFoundError:
            continue
        except RuntimeError:
            # Module found but has neither flow nor crew — keep trying
            continue

    raise RuntimeError(
        f"Could not find a valid agent module in {agent_dir}. "
        "Expected agent.py or crew.py exposing a `flow` or `crew` attribute."
    )


@app.on_event("startup")
async def startup() -> None:
    """Load the agent on server startup."""
    _load_agent()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        framework="crewai",
        mode=_mode,
    )


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest) -> InvokeResponse:
    if _agent_obj is None:
        raise HTTPException(status_code=503, detail="Agent not loaded")
    try:
        input_data = {"prompt": request.input, **request.config}
        output = await _dispatch(_agent_obj, _mode, input_data)
        return InvokeResponse(output=output, mode=_mode)
    except Exception as exc:
        logger.exception("Invocation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

### Step 3.4 — Confirm tests pass

- [ ] Run:
```bash
pytest tests/unit/test_crewai_advanced.py::TestCrewAIServerFlowDetection tests/unit/test_crewai_advanced.py::TestCrewAIServerFlowDispatch -v
```
Expected: all 6 tests green.

Confirm the build test that checks the server template is still copied correctly:
```bash
pytest tests/unit/test_runtime_crewai.py::TestCrewAIRuntimeBuild::test_build_copies_server_template -v
```

### Step 3.5 — Commit

- [ ] Commit with message:
```
feat(crewai-server): detect flow vs crew at startup, dispatch via _detect_mode/_dispatch

Server template now supports CrewAI 0.80+ Flow objects alongside classic
Crew objects. flow.kickoff_async() is used for flows; crew.kickoff() runs
in a thread executor for crews. /health echoes the active mode.
```

---

## Task 4: Add structured output validation to `crewai_server.py`

**What:** When `agent.yaml` sets `output_schema: <ref>`, the build pipeline will write the schema as a JSON string in the `AGENT_OUTPUT_SCHEMA` env var (added in this task). The `/invoke` handler attempts to parse the crew/flow result as JSON and validate it against the schema using Pydantic's `model_validate` with a dynamically created model. If validation fails, the raw string output is still returned but an `output_schema_errors` field is populated in the response.

### Step 4.1 — Wire `output_schema` into `agent.yaml` and the build

- [ ] In `engine/config_parser.py`, add `output_schema: str | None = None` to `AgentConfig` (the field already exists in the YAML spec but may not be in the Pydantic model — check and add if absent).

- [ ] In `engine/runtimes/crewai.py` `build()`, if `config.output_schema` is not `None`, add:
```python
ENV AGENT_OUTPUT_SCHEMA_REF={config.output_schema}
```
to the Dockerfile ENV block (this is a registry ref; the actual JSON schema resolution is out of scope for Phase 4 — only the env var plumbing is wired here).

### Step 4.2 — Write the failing tests

- [ ] Append to `tests/unit/test_crewai_advanced.py`:

```python
import json


# ---------------------------------------------------------------------------
# Task 4: Structured output validation
# ---------------------------------------------------------------------------

class TestCrewAIServerStructuredOutput:
    """Tests for the _validate_output helper in crewai_server."""

    def _get_validate_fn(self) -> Any:
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "crewai_server",
            pathlib.Path("engine/runtimes/templates/crewai_server.py"),
        )
        srv = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(srv)  # type: ignore[union-attr]
        return srv._validate_output

    def test_validate_output_returns_none_when_no_schema(self) -> None:
        fn = self._get_validate_fn()
        errors = fn("any string", schema=None)
        assert errors is None

    def test_validate_output_passes_valid_json(self) -> None:
        fn = self._get_validate_fn()
        schema = {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        }
        errors = fn(json.dumps({"answer": "Paris"}), schema=schema)
        assert errors is None

    def test_validate_output_catches_missing_required_field(self) -> None:
        fn = self._get_validate_fn()
        schema = {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        }
        errors = fn(json.dumps({"wrong_key": "x"}), schema=schema)
        assert errors is not None
        assert len(errors) > 0

    def test_validate_output_catches_non_json_output(self) -> None:
        fn = self._get_validate_fn()
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        errors = fn("this is not json", schema=schema)
        assert errors is not None

    def test_validate_output_catches_wrong_type(self) -> None:
        fn = self._get_validate_fn()
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"],
        }
        errors = fn(json.dumps({"count": "not-an-int"}), schema=schema)
        assert errors is not None


class TestCrewAIServerInvokeResponseSchema:
    def test_invoke_response_has_output_schema_errors_field(self) -> None:
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "crewai_server",
            pathlib.Path("engine/runtimes/templates/crewai_server.py"),
        )
        srv = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(srv)  # type: ignore[union-attr]
        # InvokeResponse must have output_schema_errors field
        resp = srv.InvokeResponse(output="hello", mode="crew", output_schema_errors=None)
        assert hasattr(resp, "output_schema_errors")

    def test_invoke_response_output_schema_errors_defaults_none(self) -> None:
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "crewai_server",
            pathlib.Path("engine/runtimes/templates/crewai_server.py"),
        )
        srv = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(srv)  # type: ignore[union-attr]
        resp = srv.InvokeResponse(output="hello", mode="crew")
        assert resp.output_schema_errors is None
```

### Step 4.3 — Confirm tests fail

- [ ] Run:
```bash
pytest tests/unit/test_crewai_advanced.py::TestCrewAIServerStructuredOutput tests/unit/test_crewai_advanced.py::TestCrewAIServerInvokeResponseSchema -v 2>&1 | head -30
```
Expected: `AttributeError: module 'crewai_server' has no attribute '_validate_output'` for structured output tests; `InvokeResponse` field test fails.

### Step 4.4 — Implement in `engine/runtimes/templates/crewai_server.py`

- [ ] Add `import json` and `import jsonschema` to the imports block at the top of the file.

- [ ] Update `InvokeResponse` to include the new field:

```python
class InvokeResponse(BaseModel):
    output: str
    mode: str = "crew"
    output_schema_errors: list[str] | None = None
```

- [ ] Add the `_validate_output` helper after `_dispatch`:

```python
def _validate_output(
    output: str, schema: dict[str, Any] | None
) -> list[str] | None:
    """Validate *output* against a JSON Schema dict.

    Returns None if validation passes or schema is None.
    Returns a list of error strings if validation fails.
    """
    if schema is None:
        return None
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        return [f"Output is not valid JSON: {exc}"]
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if not errors:
        return None
    return [f"{'.'.join(str(p) for p in e.path) or '(root)'}: {e.message}" for e in errors]
```

- [ ] Load the output schema at startup from the `AGENT_OUTPUT_SCHEMA` env var (a raw JSON string), storing it in a module-level variable:

```python
# Module-level state populated at startup
_mode: str = "crew"
_agent_obj: Any = None
_output_schema: dict[str, Any] | None = None
```

In `_load_agent()`, add after the mode detection:

```python
    raw_schema = os.environ.get("AGENT_OUTPUT_SCHEMA")
    if raw_schema:
        try:
            _output_schema = json.loads(raw_schema)
            logger.info("Loaded output schema with %d top-level properties", len(_output_schema.get("properties", {})))
        except json.JSONDecodeError:
            logger.warning("AGENT_OUTPUT_SCHEMA env var is not valid JSON — ignoring")
```

- [ ] Update the `/invoke` handler to call `_validate_output` and attach errors to the response:

```python
@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest) -> InvokeResponse:
    if _agent_obj is None:
        raise HTTPException(status_code=503, detail="Agent not loaded")
    try:
        input_data = {"prompt": request.input, **request.config}
        output = await _dispatch(_agent_obj, _mode, input_data)
        schema_errors = _validate_output(output, _output_schema)
        return InvokeResponse(output=output, mode=_mode, output_schema_errors=schema_errors)
    except Exception as exc:
        logger.exception("Invocation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

### Step 4.5 — Confirm tests pass

- [ ] Run:
```bash
pytest tests/unit/test_crewai_advanced.py::TestCrewAIServerStructuredOutput tests/unit/test_crewai_advanced.py::TestCrewAIServerInvokeResponseSchema -v
```
Expected: all 7 tests green.

Confirm Task 3 tests are still green:
```bash
pytest tests/unit/test_crewai_advanced.py::TestCrewAIServerFlowDetection tests/unit/test_crewai_advanced.py::TestCrewAIServerFlowDispatch -v
```

### Step 4.6 — Commit

- [ ] Commit with message:
```
feat(crewai-server): structured output validation via AGENT_OUTPUT_SCHEMA env var

_validate_output() uses jsonschema Draft7Validator to check crew/flow output
against a JSON Schema loaded from AGENT_OUTPUT_SCHEMA at startup. Validation
errors are returned in InvokeResponse.output_schema_errors without blocking
the response, so callers can decide how to handle schema mismatches.
```

---

## Task 5: Integration test — hierarchical crew invocation end-to-end

**What:** Write a module-level integration test that exercises the full path from `agent.yaml` parsing → `CrewAIRuntime.build()` → Dockerfile content inspection → server template startup detection. No live CrewAI invocation is required (the integration test mocks `crew.kickoff`). This confirms all four tasks compose correctly: the `crewai:` block in YAML is parsed into `CrewAIConfig`, surfaced in `AgentConfig`, written into the Dockerfile, and the server template's detection and dispatch logic handles a hierarchical crew correctly.

### Step 5.1 — Write the integration test

- [ ] Append to `tests/unit/test_crewai_advanced.py`:

```python
# ---------------------------------------------------------------------------
# Task 5: Integration — hierarchical crew end-to-end (no live CrewAI)
# ---------------------------------------------------------------------------

class TestHierarchicalCrewEndToEnd:
    """Simulate the full deploy pipeline for a hierarchical crew agent.

    Covers: YAML parse -> AgentConfig.crewai populated -> build() writes
    correct ENV vars -> server template detects crew mode and dispatches.
    """

    _AGENT_YAML = """\
name: support-agent
version: 1.0.0
team: eng
owner: dev@example.com
framework: crewai
model:
  primary: claude-sonnet-4
  temperature: 0.3
  max_tokens: 2048
deploy:
  cloud: local
crewai:
  process: hierarchical
  manager_llm: claude-opus-4
  verbose: true
  memory: true
"""

    def test_yaml_parses_to_crewai_config(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(self._AGENT_YAML)
        from engine.config_parser import parse_config
        config = parse_config(yaml_file)
        assert config.crewai is not None
        assert config.crewai.process == "hierarchical"
        assert config.crewai.manager_llm == "claude-opus-4"
        assert config.crewai.verbose is True
        assert config.crewai.memory is True

    def test_build_dockerfile_contains_all_crewai_env_vars(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(self._AGENT_YAML)
        from engine.config_parser import parse_config
        from engine.runtimes.crewai import CrewAIRuntime
        config = parse_config(yaml_file)
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "crew.py").write_text("crew = None\n")
        (agent_dir / "requirements.txt").write_text("crewai\n")
        image = CrewAIRuntime().build(agent_dir, config)
        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "ENV AGENT_CREWAI_PROCESS=hierarchical" in dockerfile
        assert "ENV AGENT_CREWAI_MANAGER_LLM=claude-opus-4" in dockerfile
        assert "ENV AGENT_CREWAI_VERBOSE=true" in dockerfile
        assert "ENV AGENT_CREWAI_MEMORY=true" in dockerfile

    def test_build_requirements_include_crewai_tools(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(self._AGENT_YAML)
        from engine.config_parser import parse_config
        from engine.runtimes.crewai import CrewAIRuntime
        config = parse_config(yaml_file)
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "crew.py").write_text("crew = None\n")
        (agent_dir / "requirements.txt").write_text("crewai\n")
        image = CrewAIRuntime().build(agent_dir, config)
        req_text = (image.context_dir / "requirements.txt").read_text()
        assert "crewai-tools" in req_text

    def test_server_detects_crew_mode_for_hierarchical_agent(self) -> None:
        import importlib.util, pathlib, types
        spec = importlib.util.spec_from_file_location(
            "crewai_server",
            pathlib.Path("engine/runtimes/templates/crewai_server.py"),
        )
        srv = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(srv)  # type: ignore[union-attr]

        mod = types.ModuleType("agent")
        crew_mock = MagicMock()
        crew_mock.kickoff = MagicMock(return_value="ticket resolved")
        mod.crew = crew_mock

        mode, obj = srv._detect_mode(mod)
        assert mode == "crew"
        assert obj is crew_mock

    def test_server_dispatches_crew_kickoff_and_returns_result(self) -> None:
        import importlib.util, pathlib, types
        spec = importlib.util.spec_from_file_location(
            "crewai_server",
            pathlib.Path("engine/runtimes/templates/crewai_server.py"),
        )
        srv = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(srv)  # type: ignore[union-attr]

        crew_mock = MagicMock()
        crew_mock.kickoff = MagicMock(return_value="ticket resolved")

        result = asyncio.get_event_loop().run_until_complete(
            srv._dispatch(crew_mock, "crew", {"prompt": "resolve ticket #42"})
        )
        crew_mock.kickoff.assert_called_once()
        assert result == "ticket resolved"

    def test_schema_validates_full_hierarchical_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(self._AGENT_YAML)
        from engine.config_parser import validate_config
        result = validate_config(yaml_file)
        assert result.valid, result.errors
```

### Step 5.2 — Confirm tests fail

- [ ] Run:
```bash
pytest tests/unit/test_crewai_advanced.py::TestHierarchicalCrewEndToEnd -v 2>&1 | head -40
```
Expected: failures due to missing `crewai:` parse support (Task 1 not yet implemented in isolation here — tests confirm the full stack). If Tasks 1–4 are already committed, all should pass immediately at Step 5.4.

### Step 5.3 — No new implementation required

Tasks 1–4 provide all the implementation. This task is purely additive tests that confirm integration.

### Step 5.4 — Run the full advanced test suite

- [ ] Run:
```bash
pytest tests/unit/test_crewai_advanced.py -v
```
Expected: all tests green (approximately 37 tests total).

Also run the existing CrewAI unit tests to confirm no regressions:
```bash
pytest tests/unit/test_runtime_crewai.py -v
```

And the config parser tests:
```bash
pytest tests/unit/test_config_parser.py -v
```

### Step 5.5 — Commit

- [ ] Commit with message:
```
test(crewai): integration tests for hierarchical crew end-to-end pipeline

TestHierarchicalCrewEndToEnd validates the full path from agent.yaml parse
through Dockerfile generation to server template dispatch for a hierarchical
crewai: config block.
```

---

## Phase 4 Complete — Verification

Run the full Phase 4 test suite plus all related unit tests:

```bash
pytest tests/unit/test_crewai_advanced.py tests/unit/test_runtime_crewai.py tests/unit/test_config_parser.py -v --tb=short
```

All tests must be green before marking Phase 4 done.

Check coverage on the changed files:

```bash
pytest tests/unit/test_crewai_advanced.py tests/unit/test_runtime_crewai.py \
  --cov=engine/runtimes/crewai \
  --cov=engine/runtimes/templates/crewai_server \
  --cov=engine/config_parser \
  --cov-report=term-missing \
  --tb=short
```

Target: >= 90% branch coverage on `crewai.py`, `crewai_server.py`, and the new `CrewAIConfig` in `config_parser.py`.
