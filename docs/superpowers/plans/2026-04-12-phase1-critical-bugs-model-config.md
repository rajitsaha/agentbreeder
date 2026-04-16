# Phase 1: Critical Bugs + Model Config Forwarding

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three production bugs (ADK session leak, Claude hardcoded max_tokens, missing Dockerfile env_vars) and ensure all `agent.yaml` model fields reach every framework at runtime.

**Architecture:** All three `build()` methods gain a `_build_env_block(config)` helper that emits `ENV` directives into the Dockerfile. Server templates read `AGENT_MODEL`, `AGENT_TEMPERATURE`, `AGENT_MAX_TOKENS`, `AGENT_SYSTEM_PROMPT` from env. The ADK server template is refactored to hold a module-level `_session_service` and reuse `_runner` across requests with per-request sessions.

**Tech Stack:** Python 3.11+, FastAPI, google-adk>=1.0.0, anthropic>=0.40.0, crewai>=0.80.0, pytest

---

## Task 1: Fix BUG-2 — Claude SDK `max_tokens` hardcoded to 1024

**Files:**
- Modify: `engine/runtimes/templates/claude_sdk_server.py`
- Test: `tests/unit/test_runtime_claude_sdk.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/test_runtime_claude_sdk.py`:

```python
import os
from unittest.mock import AsyncMock, MagicMock, patch


class TestClaudeSDKServerMaxTokens:
    """max_tokens must come from AGENT_MAX_TOKENS env var, not be hardcoded."""

    def test_build_sets_agent_max_tokens_env_var(self) -> None:
        """build() must write AGENT_MAX_TOKENS into the Dockerfile."""
        runtime = ClaudeSDKRuntime()
        agent_dir = _make_agent_dir(
            {
                "agent.py": "agent = None",
                "requirements.txt": "anthropic>=0.40.0",
            }
        )
        config = _make_config(model={"primary": "claude-opus-4-6", "max_tokens": 4096})
        image = runtime.build(agent_dir, config)
        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "AGENT_MAX_TOKENS" in dockerfile
        assert "4096" in dockerfile

    def test_build_omits_max_tokens_env_when_not_set(self) -> None:
        """If model.max_tokens is None, AGENT_MAX_TOKENS should not appear in Dockerfile."""
        runtime = ClaudeSDKRuntime()
        agent_dir = _make_agent_dir(
            {
                "agent.py": "agent = None",
                "requirements.txt": "anthropic>=0.40.0",
            }
        )
        # _make_config() uses no max_tokens by default
        config = _make_config()
        image = runtime.build(agent_dir, config)
        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "AGENT_MAX_TOKENS" not in dockerfile
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/rajit/personal-github/agentbreeder
pytest tests/unit/test_runtime_claude_sdk.py::TestClaudeSDKServerMaxTokens -v
```

Expected: `FAILED` — `AGENT_MAX_TOKENS` not in Dockerfile.

- [ ] **Step 3: Update `claude_sdk_server.py` — read `AGENT_MAX_TOKENS` from env**

In `engine/runtimes/templates/claude_sdk_server.py`, replace the `_run_agent` function body where `max_tokens` is set. The current code at lines ~118–138 has `"max_tokens": 1024` in two places. Replace both:

```python
async def _run_agent(input_data: str) -> str:
    """Run the agent, dispatching based on the type of object loaded from agent.py."""
    import anthropic

    model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    system_prompt = os.getenv("AGENT_SYSTEM_PROMPT", "")
    max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "1024"))
    messages = [{"role": "user", "content": input_data}]

    # anthropic.AsyncAnthropic client
    if isinstance(_agent, anthropic.AsyncAnthropic):
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        response = await _agent.messages.create(**kwargs)
        return _extract_text(response)

    # anthropic.Anthropic (sync) client — run in thread to avoid blocking
    if isinstance(_agent, anthropic.Anthropic):
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        response = await asyncio.to_thread(_agent.messages.create, **kwargs)
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

- [ ] **Step 4: Update `ClaudeSDKRuntime.build()` — write `AGENT_MAX_TOKENS` env var**

In `engine/runtimes/claude_sdk.py`, replace the `build()` method to write env vars into the Dockerfile. First, add a helper after `DOCKERFILE_TEMPLATE`:

```python
def _build_env_block(config: "AgentConfig") -> str:
    """Generate Dockerfile ENV lines from agent.yaml model + deploy config."""
    lines: list[str] = []
    lines.append(f"ENV AGENT_NAME={config.name}")
    lines.append(f"ENV AGENT_VERSION={config.version}")
    lines.append(f"ENV AGENT_FRAMEWORK=claude_sdk")
    if config.model.primary:
        lines.append(f"ENV AGENT_MODEL={config.model.primary}")
    if config.model.temperature is not None:
        lines.append(f"ENV AGENT_TEMPERATURE={config.model.temperature}")
    if config.model.max_tokens is not None:
        lines.append(f"ENV AGENT_MAX_TOKENS={config.model.max_tokens}")
    if config.prompts.system:
        # Inline system prompt — quote carefully (newlines stripped)
        safe = config.prompts.system.replace("\n", " ").replace('"', '\\"')
        lines.append(f'ENV AGENT_SYSTEM_PROMPT="{safe}"')
    for key, val in config.deploy.env_vars.items():
        safe_val = str(val).replace('"', '\\"')
        lines.append(f'ENV {key}="{safe_val}"')
    return "\n".join(lines)
```

Then in `build()`, after `dockerfile.write_text(DOCKERFILE_TEMPLATE)` replace with:

```python
env_block = _build_env_block(config)
dockerfile_content = DOCKERFILE_TEMPLATE.rstrip() + "\n\n# Agent configuration\n" + env_block + "\n"
dockerfile.write_text(dockerfile_content)
```

And update the `ContainerImage` return:

```python
return ContainerImage(
    tag=tag,
    dockerfile_content=dockerfile_content,
    context_dir=build_dir,
)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/unit/test_runtime_claude_sdk.py -v
```

Expected: all pass including the two new `TestClaudeSDKServerMaxTokens` tests.

- [ ] **Step 6: Commit**

```bash
git add engine/runtimes/templates/claude_sdk_server.py engine/runtimes/claude_sdk.py tests/unit/test_runtime_claude_sdk.py
git commit -m "fix(claude-sdk): read max_tokens from AGENT_MAX_TOKENS env; write model env vars in build()"
```

---

## Task 2: Fix BUG-3 — `build()` writes `deploy.env_vars` + model env vars (CrewAI and ADK)

**Files:**
- Modify: `engine/runtimes/crewai.py`
- Modify: `engine/runtimes/google_adk.py`
- Test: `tests/unit/test_runtime_crewai.py`
- Test: `tests/unit/test_runtime_google_adk.py`

- [ ] **Step 1: Write failing tests for CrewAI**

Add to `tests/unit/test_runtime_crewai.py`:

```python
class TestCrewAIRuntimeEnvVarInjection:
    """build() must write model config and deploy.env_vars into the Dockerfile."""

    def test_build_writes_agent_model_env_var(self) -> None:
        runtime = CrewAIRuntime()
        agent_dir = _make_agent_dir(
            {"crew.py": "crew = None", "requirements.txt": "crewai>=0.80.0"}
        )
        config = _make_config(model={"primary": "claude-opus-4-6"})
        image = runtime.build(agent_dir, config)
        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "AGENT_MODEL" in dockerfile
        assert "claude-opus-4-6" in dockerfile

    def test_build_writes_temperature_env_var(self) -> None:
        runtime = CrewAIRuntime()
        agent_dir = _make_agent_dir(
            {"crew.py": "crew = None", "requirements.txt": "crewai>=0.80.0"}
        )
        config = _make_config(model={"primary": "gpt-4o", "temperature": 0.3})
        image = runtime.build(agent_dir, config)
        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "AGENT_TEMPERATURE" in dockerfile
        assert "0.3" in dockerfile

    def test_build_writes_deploy_env_vars(self) -> None:
        runtime = CrewAIRuntime()
        agent_dir = _make_agent_dir(
            {"crew.py": "crew = None", "requirements.txt": "crewai>=0.80.0"}
        )
        config = _make_config(
            deploy={"cloud": "local", "env_vars": {"SERPER_API_KEY": "test-key", "LOG_LEVEL": "debug"}}
        )
        image = runtime.build(agent_dir, config)
        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "SERPER_API_KEY" in dockerfile
        assert "test-key" in dockerfile
        assert "LOG_LEVEL" in dockerfile

    def test_build_skips_optional_env_vars_when_not_set(self) -> None:
        runtime = CrewAIRuntime()
        agent_dir = _make_agent_dir(
            {"crew.py": "crew = None", "requirements.txt": "crewai>=0.80.0"}
        )
        config = _make_config()  # no temperature, no max_tokens
        image = runtime.build(agent_dir, config)
        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "AGENT_TEMPERATURE" not in dockerfile
        assert "AGENT_MAX_TOKENS" not in dockerfile
```

- [ ] **Step 2: Write failing tests for ADK**

Add to `tests/unit/test_runtime_google_adk.py`:

```python
class TestGoogleADKRuntimeEnvVarInjection:
    def test_build_writes_agent_model_env_var(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {"agent.py": "root_agent = None", "requirements.txt": "google-adk>=0.3.0"},
        )
        config = _make_config(model={"primary": "gemini-1.5-pro"})
        image = runtime.build(agent_dir, config)
        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "AGENT_MODEL" in dockerfile
        assert "gemini-1.5-pro" in dockerfile

    def test_build_writes_deploy_env_vars(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {"agent.py": "root_agent = None", "requirements.txt": "google-adk>=0.3.0"},
        )
        config = _make_config(
            deploy={"cloud": "gcp", "env_vars": {"GOOGLE_CLOUD_PROJECT": "my-proj"}}
        )
        image = runtime.build(agent_dir, config)
        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "GOOGLE_CLOUD_PROJECT" in dockerfile
        assert "my-proj" in dockerfile
```

- [ ] **Step 3: Run to confirm failures**

```bash
pytest tests/unit/test_runtime_crewai.py::TestCrewAIRuntimeEnvVarInjection tests/unit/test_runtime_google_adk.py::TestGoogleADKRuntimeEnvVarInjection -v
```

Expected: all `FAILED`.

- [ ] **Step 4: Add `_build_env_block` to `engine/runtimes/crewai.py`**

After the `DOCKERFILE_TEMPLATE` constant, add:

```python
def _build_env_block(config: "AgentConfig") -> str:
    """Generate Dockerfile ENV lines from agent.yaml model + deploy config."""
    lines: list[str] = [
        f"ENV AGENT_NAME={config.name}",
        f"ENV AGENT_VERSION={config.version}",
        "ENV AGENT_FRAMEWORK=crewai",
    ]
    if config.model.primary:
        lines.append(f"ENV AGENT_MODEL={config.model.primary}")
    if config.model.temperature is not None:
        lines.append(f"ENV AGENT_TEMPERATURE={config.model.temperature}")
    if config.model.max_tokens is not None:
        lines.append(f"ENV AGENT_MAX_TOKENS={config.model.max_tokens}")
    if config.prompts.system:
        safe = config.prompts.system.replace("\n", " ").replace('"', '\\"')
        lines.append(f'ENV AGENT_SYSTEM_PROMPT="{safe}"')
    for key, val in config.deploy.env_vars.items():
        safe_val = str(val).replace('"', '\\"')
        lines.append(f'ENV {key}="{safe_val}"')
    return "\n".join(lines)
```

Then in `CrewAIRuntime.build()`, replace the two lines that write the Dockerfile:

```python
# Write Dockerfile
dockerfile = build_dir / "Dockerfile"
env_block = _build_env_block(config)
dockerfile_content = DOCKERFILE_TEMPLATE.rstrip() + "\n\n# Agent configuration\n" + env_block + "\n"
dockerfile.write_text(dockerfile_content)

tag = f"agentbreeder/{config.name}:{config.version}"

return ContainerImage(
    tag=tag,
    dockerfile_content=dockerfile_content,
    context_dir=build_dir,
)
```

- [ ] **Step 5: Add `_build_env_block` to `engine/runtimes/google_adk.py`**

After `DOCKERFILE_TEMPLATE`, add:

```python
def _build_env_block(config: "AgentConfig") -> str:
    """Generate Dockerfile ENV lines from agent.yaml model + deploy config."""
    lines: list[str] = [
        f"ENV AGENT_NAME={config.name}",
        f"ENV AGENT_VERSION={config.version}",
        "ENV AGENT_FRAMEWORK=google_adk",
    ]
    if config.model.primary:
        lines.append(f"ENV AGENT_MODEL={config.model.primary}")
    if config.model.temperature is not None:
        lines.append(f"ENV AGENT_TEMPERATURE={config.model.temperature}")
    if config.model.max_tokens is not None:
        lines.append(f"ENV AGENT_MAX_TOKENS={config.model.max_tokens}")
    for key, val in config.deploy.env_vars.items():
        safe_val = str(val).replace('"', '\\"')
        lines.append(f'ENV {key}="{safe_val}"')
    return "\n".join(lines)
```

Apply the same Dockerfile write pattern in `GoogleADKRuntime.build()` as in Task 2 Step 4.

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/unit/test_runtime_crewai.py tests/unit/test_runtime_google_adk.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add engine/runtimes/crewai.py engine/runtimes/google_adk.py \
        tests/unit/test_runtime_crewai.py tests/unit/test_runtime_google_adk.py
git commit -m "fix: write model config and deploy.env_vars as ENV in all three runtime Dockerfiles"
```

---

## Task 3: Fix BUG-1 — Google ADK per-request Runner + SessionService leak

**Files:**
- Modify: `engine/runtimes/templates/google_adk_server.py`
- Test: `tests/unit/test_runtime_google_adk.py` (server template behavior)

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_runtime_google_adk.py`:

```python
import importlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock, call, patch


class TestGoogleADKServerRunnerReuse:
    """The module-level _runner must be reused across requests."""

    def test_invoke_request_schema_accepts_session_id(self) -> None:
        """InvokeRequest should have an optional session_id field."""
        # We test the schema by importing the server module with mocked google.adk deps
        # Build a minimal fake google.adk namespace so the import succeeds
        fake_adk = types.ModuleType("google.adk")
        fake_runners = types.ModuleType("google.adk.runners")
        fake_sessions = types.ModuleType("google.adk.sessions")
        fake_runner_cls = MagicMock()
        fake_sessions.InMemorySessionService = MagicMock()
        fake_runners.Runner = fake_runner_cls
        sys.modules.setdefault("google", types.ModuleType("google"))
        sys.modules["google.adk"] = fake_adk
        sys.modules["google.adk.runners"] = fake_runners
        sys.modules["google.adk.sessions"] = fake_sessions

        # Dynamically load the server template
        spec = importlib.util.spec_from_file_location(
            "google_adk_server",
            "engine/runtimes/templates/google_adk_server.py",
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        req = mod.InvokeRequest(input="hello")
        assert hasattr(req, "session_id"), "InvokeRequest must have session_id field"
        assert req.session_id is None  # default None

        req_with_session = mod.InvokeRequest(input="hello", session_id="abc-123")
        assert req_with_session.session_id == "abc-123"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_runtime_google_adk.py::TestGoogleADKServerRunnerReuse -v
```

Expected: `FAILED` — `InvokeRequest` has no `session_id` field.

- [ ] **Step 3: Rewrite `google_adk_server.py` to fix BUG-1**

Replace the entire file content of `engine/runtimes/templates/google_adk_server.py`:

```python
"""AgentBreeder server wrapper for Google ADK agents.

This file is copied into the agent container at build time.
It wraps any Google ADK agent as a FastAPI server with /invoke and /health endpoints.

Authentication: uses Application Default Credentials (ADC).
Set GOOGLE_APPLICATION_CREDENTIALS to a service account key path, or rely on
Workload Identity when running on GCP.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentbreeder.agent")

app = FastAPI(
    title="AgentBreeder Agent",
    description="Deployed by AgentBreeder",
    version=os.getenv("AGENT_VERSION", "0.1.0"),
)


class InvokeRequest(BaseModel):
    input: str
    session_id: str | None = None  # pass to maintain conversation history
    config: dict[str, Any] | None = None


class InvokeResponse(BaseModel):
    output: Any
    session_id: str  # echo back so caller can continue conversation
    metadata: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    agent_name: str
    version: str


def _load_agent() -> Any:
    """Dynamically load the ADK agent from agent.py."""
    sys.path.insert(0, "/app")
    try:
        module = importlib.import_module("agent")
    except ImportError as e:
        logger.error("Failed to import agent module: %s", e)
        raise

    for attr_name in ("root_agent", "agent", "app"):
        if hasattr(module, attr_name):
            return getattr(module, attr_name)

    msg = (
        "agent.py must export one of: 'root_agent', 'agent', or 'app'. "
        "This should be a google.adk.agents.Agent instance."
    )
    raise AttributeError(msg)


# Module-level singletons — initialized once at startup, reused for all requests
_agent = None
_runner = None
_session_service = None


@app.on_event("startup")
async def startup() -> None:
    global _agent, _runner, _session_service  # noqa: PLW0603
    logger.info("Loading Google ADK agent...")
    _agent = _load_agent()

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    app_name = os.getenv("GOOGLE_CLOUD_PROJECT", "agentbreeder-local")
    _session_service = InMemorySessionService()
    _runner = Runner(
        agent=_agent,
        app_name=app_name,
        session_service=_session_service,
    )
    logger.info("Google ADK agent loaded successfully (app_name=%s)", app_name)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy" if _agent is not None else "loading",
        agent_name=os.getenv("AGENT_NAME", "unknown"),
        version=os.getenv("AGENT_VERSION", "0.1.0"),
    )


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest) -> InvokeResponse:
    if _agent is None or _runner is None or _session_service is None:
        raise HTTPException(status_code=503, detail="Agent not loaded yet")

    # Reuse provided session_id or create a new one for this call
    session_id = request.session_id or str(uuid.uuid4())
    config = request.config or {}
    user_id = config.get("user_id", "agentbreeder-user")

    try:
        result = await _run_agent(request.input, session_id, user_id)
        return InvokeResponse(output=result, session_id=session_id)
    except Exception as e:
        logger.exception("Agent invocation failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _run_agent(input_text: str, session_id: str, user_id: str) -> str:
    """Run the Google ADK agent using the module-level runner and session service."""
    from google.genai import types as genai_types

    app_name = os.getenv("GOOGLE_CLOUD_PROJECT", "agentbreeder-local")

    # Look up existing session or create a new one
    existing = await _session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if existing is None:
        session = await _session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
    else:
        session = existing

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=input_text)],
    )

    final_response = ""
    async for event in _runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_response += part.text

    return final_response
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_runtime_google_adk.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add engine/runtimes/templates/google_adk_server.py tests/unit/test_runtime_google_adk.py
git commit -m "fix(google-adk): reuse module-level Runner across requests; add session_id to InvokeRequest"
```

---

## Task 4: Forward `AGENT_MODEL` + `AGENT_TEMPERATURE` in CrewAI server template

**Files:**
- Modify: `engine/runtimes/templates/crewai_server.py`
- Test: `tests/unit/test_runtime_crewai.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_runtime_crewai.py`:

```python
class TestCrewAIServerModelConfig:
    """The server template must read AGENT_MODEL / AGENT_TEMPERATURE from env."""

    def test_server_template_references_agent_model_env(self) -> None:
        """crewai_server.py must read AGENT_MODEL (not hard-code a model name)."""
        server_text = (
            Path("engine/runtimes/templates/crewai_server.py").read_text()
        )
        assert "AGENT_MODEL" in server_text, (
            "crewai_server.py must read AGENT_MODEL env var to allow model override"
        )

    def test_server_template_references_agent_temperature_env(self) -> None:
        server_text = (
            Path("engine/runtimes/templates/crewai_server.py").read_text()
        )
        assert "AGENT_TEMPERATURE" in server_text
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_runtime_crewai.py::TestCrewAIServerModelConfig -v
```

Expected: `FAILED`.

- [ ] **Step 3: Update `crewai_server.py` startup to inject model config**

In `engine/runtimes/templates/crewai_server.py`, update the `startup()` handler to read env vars and patch the crew's agents' LLM config after loading:

```python
@app.on_event("startup")
async def startup() -> None:
    global _crew  # noqa: PLW0603
    logger.info("Loading CrewAI crew...")
    _crew = _load_agent()

    # Apply model config from env vars if the crew has agents
    agent_model = os.getenv("AGENT_MODEL")
    agent_temperature_str = os.getenv("AGENT_TEMPERATURE")
    agent_temperature = float(agent_temperature_str) if agent_temperature_str else None

    if agent_model and hasattr(_crew, "agents"):
        try:
            from crewai import LLM

            llm_kwargs: dict[str, Any] = {"model": agent_model}
            if agent_temperature is not None:
                llm_kwargs["temperature"] = agent_temperature
            override_llm = LLM(**llm_kwargs)
            for agent in _crew.agents:
                agent.llm = override_llm
            logger.info(
                "Applied model override to %d agent(s): model=%s temperature=%s",
                len(_crew.agents),
                agent_model,
                agent_temperature,
            )
        except Exception:
            logger.warning("Could not apply AGENT_MODEL override — proceeding with crew defaults")

    logger.info("CrewAI crew loaded successfully")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_runtime_crewai.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add engine/runtimes/templates/crewai_server.py tests/unit/test_runtime_crewai.py
git commit -m "feat(crewai): apply AGENT_MODEL and AGENT_TEMPERATURE env vars to crew agents at startup"
```

---

## Task 5: Forward `AGENT_MODEL` + `AGENT_TEMPERATURE` in ADK server template

**Files:**
- Modify: `engine/runtimes/templates/google_adk_server.py`
- Test: `tests/unit/test_runtime_google_adk.py`

- [ ] **Step 1: Write failing test**

```python
class TestGoogleADKServerModelConfig:
    def test_server_template_references_agent_model_env(self) -> None:
        server_text = Path("engine/runtimes/templates/google_adk_server.py").read_text()
        assert "AGENT_MODEL" in server_text
```

- [ ] **Step 2: Update `google_adk_server.py` `startup()` to apply model override**

In `startup()` in `google_adk_server.py`, after `_agent = _load_agent()`, add:

```python
# Apply AGENT_MODEL override if the loaded agent is an LlmAgent
agent_model = os.getenv("AGENT_MODEL")
agent_temperature_str = os.getenv("AGENT_TEMPERATURE")
agent_max_tokens_str = os.getenv("AGENT_MAX_TOKENS")

if agent_model and hasattr(_agent, "model"):
    try:
        _agent.model = agent_model
        logger.info("Applied AGENT_MODEL override: %s", agent_model)
    except Exception:
        logger.warning("Could not set AGENT_MODEL on agent — proceeding with agent default")

if (agent_temperature_str or agent_max_tokens_str) and hasattr(_agent, "generate_content_config"):
    try:
        from google.genai import types as genai_types

        existing = _agent.generate_content_config or genai_types.GenerateContentConfig()
        kwargs: dict[str, Any] = {}
        if agent_temperature_str:
            kwargs["temperature"] = float(agent_temperature_str)
        if agent_max_tokens_str:
            kwargs["max_output_tokens"] = int(agent_max_tokens_str)
        _agent.generate_content_config = genai_types.GenerateContentConfig(
            **{
                **({
                    "temperature": existing.temperature,
                    "max_output_tokens": existing.max_output_tokens,
                } if existing else {}),
                **kwargs,
            }
        )
        logger.info("Applied generate_content_config overrides: %s", kwargs)
    except Exception:
        logger.warning("Could not apply generate_content_config — proceeding with agent defaults")
```

- [ ] **Step 3: Run all unit tests**

```bash
pytest tests/unit/ -v --tb=short
```

Expected: all pass.

- [ ] **Step 4: Final commit for Phase 1**

```bash
git add engine/runtimes/templates/google_adk_server.py tests/unit/test_runtime_google_adk.py
git commit -m "feat(google-adk): apply AGENT_MODEL, AGENT_TEMPERATURE, AGENT_MAX_TOKENS at startup"
```

---

## Phase 1 Complete — Verification

```bash
# Run full unit test suite
pytest tests/unit/ -v --tb=short

# Check coverage on changed files
pytest tests/unit/ --cov=engine/runtimes --cov-report=term-missing

# Lint
ruff check engine/runtimes/ tests/unit/
```

Expected: all unit tests pass, coverage ≥ 95% on modified files, no lint errors.
