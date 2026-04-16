# Ollama/LiteLLM Support Across All Runtimes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all AgentBreeder runtimes work with `model: ollama/*` in `agent.yaml`, with the local deployer automatically starting the Ollama sidecar and pulling model weights.

**Architecture:** Each runtime gets three changes: (1) `litellm>=1.40.0` added to `get_requirements()` when the model is `ollama/`, (2) `OLLAMA_BASE_URL` injected into the Dockerfile ENV block, (3) server template updated to route through LiteLLM/Ollama where it controls the model. The `DockerComposeDeployer` gets an Ollama sidecar that starts automatically and pulls the model before the agent container starts. Claude SDK emits a validation error (it's Anthropic-only).

**Tech Stack:** `litellm>=1.40.0`, `docker` Python SDK, Ollama REST API via `exec_run`.

**GitHub Issues resolved:** #63 (all runtimes), #64 (sidecar auto-injection), #65 (auto model pull), #66 (Google ADK root_agent.yaml)

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `engine/runtimes/langgraph.py` | Modify | `get_requirements()` + env block in `build()` |
| `engine/runtimes/openai_agents.py` | Modify | `get_requirements()` + env block in `build()` |
| `engine/runtimes/custom.py` | Modify | `get_requirements()` + env block in `build()` (fallback mode only) |
| `engine/runtimes/templates/openai_agents_server.py` | Modify | Startup: configure `AsyncOpenAI` with Ollama endpoint |
| `engine/runtimes/crewai.py` | Modify | `get_requirements()` |
| `engine/runtimes/templates/crewai_server.py` | Modify | Startup: set `agent.llm.base_url` for `ollama/` models |
| `engine/runtimes/google_adk.py` | Modify | `get_requirements()` + `SERVER_LOADER_CONTENT` fallback Agent construction |
| `engine/runtimes/templates/google_adk_server.py` | Modify | Lifespan: use `LiteLlm` instead of raw string for `ollama/` models |
| `engine/runtimes/claude_sdk.py` | Modify | `validate()`: block `ollama/` models with a clear error |
| `engine/deployers/docker_compose.py` | Modify | `_ensure_ollama_sidecar()`, `_pull_ollama_model()`, wire into `deploy()` |
| `tests/unit/test_runtimes.py` | Modify | Add Ollama requirements + env var tests for LangGraph |
| `tests/unit/test_runtime_crewai.py` | Modify | Add Ollama requirements + base_url injection tests |
| `tests/unit/test_openai_agents_runtime.py` | Modify | Add Ollama requirements + env var tests |
| `tests/unit/test_runtime_google_adk.py` | Modify | Add Ollama requirements + LiteLlm injection tests |
| `tests/unit/test_runtime_claude_sdk.py` | Modify | Add Ollama validation error test |
| `tests/unit/test_docker_compose_deployer.py` | Modify | Add sidecar injection + model pull tests |

---

## Task 1: LangGraph, OpenAI Agents, Custom — litellm dep + Dockerfile ENV

These three runtimes don't inject an env block today. Add it, and conditionally include `litellm` + `OLLAMA_BASE_URL`.

**Files:**
- Modify: `engine/runtimes/langgraph.py`
- Modify: `engine/runtimes/openai_agents.py`
- Modify: `engine/runtimes/custom.py`
- Modify: `tests/unit/test_runtimes.py`
- Modify: `tests/unit/test_openai_agents_runtime.py`

- [ ] **Step 1: Write failing tests**

In `tests/unit/test_runtimes.py`, find the `TestLangGraphRuntime` class and append these tests after the existing `test_get_requirements` test:

```python
def test_get_requirements_adds_litellm_for_ollama_model(self) -> None:
    from engine.runtimes.langgraph import LangGraphRuntime

    config = make_agent_config(model_primary="ollama/gemma3:27b")
    runtime = LangGraphRuntime()
    reqs = runtime.get_requirements(config)
    assert any("litellm" in r for r in reqs)

def test_build_injects_ollama_base_url_for_ollama_model(self, tmp_path: Path) -> None:
    from engine.runtimes.langgraph import LangGraphRuntime

    (tmp_path / "agent.py").write_text("graph = None")
    (tmp_path / "requirements.txt").write_text("")
    config = make_agent_config(model_primary="ollama/gemma3:27b")
    runtime = LangGraphRuntime()
    image = runtime.build(tmp_path, config)
    dockerfile = (image.context_dir / "Dockerfile").read_text()
    assert "OLLAMA_BASE_URL" in dockerfile

def test_build_does_not_inject_ollama_url_for_gemini_model(self, tmp_path: Path) -> None:
    from engine.runtimes.langgraph import LangGraphRuntime

    (tmp_path / "agent.py").write_text("graph = None")
    (tmp_path / "requirements.txt").write_text("")
    config = make_agent_config(model_primary="gemini-2.0-flash")
    runtime = LangGraphRuntime()
    image = runtime.build(tmp_path, config)
    dockerfile = (image.context_dir / "Dockerfile").read_text()
    assert "OLLAMA_BASE_URL" not in dockerfile
```

Check how `make_agent_config` is defined in the file (it accepts a `model_primary` kwarg or similar). If it doesn't support setting `model_primary`, check the fixture and use whatever the test file already does to create configs with different models.

In `tests/unit/test_openai_agents_runtime.py`, append after `test_get_requirements_includes_core_deps`:

```python
def test_get_requirements_adds_litellm_for_ollama_model(self) -> None:
    from engine.runtimes.openai_agents import OpenAIAgentsRuntime

    config = make_agent_config(model_primary="ollama/gemma3:27b")
    runtime = OpenAIAgentsRuntime()
    reqs = runtime.get_requirements(config)
    assert any("litellm" in r for r in reqs)

def test_build_injects_ollama_base_url(self, tmp_path: Path) -> None:
    from engine.runtimes.openai_agents import OpenAIAgentsRuntime

    (tmp_path / "agent.py").write_text("agent = None")
    (tmp_path / "requirements.txt").write_text("")
    config = make_agent_config(model_primary="ollama/gemma3:27b")
    runtime = OpenAIAgentsRuntime()
    image = runtime.build(tmp_path, config)
    dockerfile = (image.context_dir / "Dockerfile").read_text()
    assert "OLLAMA_BASE_URL" in dockerfile
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/rajit/personal-github/agentbreeder
python3 -m pytest tests/unit/test_runtimes.py -k "ollama" -v
python3 -m pytest tests/unit/test_openai_agents_runtime.py -k "ollama" -v
```

Expected: `FAILED` — attribute errors or assertion errors because litellm and OLLAMA_BASE_URL aren't injected yet.

- [ ] **Step 3: Fix `engine/runtimes/langgraph.py`**

Add `build_env_block` to the import line (currently line 14):

```python
from engine.runtimes.base import ContainerImage, RuntimeBuilder, RuntimeValidationResult, build_env_block
```

Replace `get_requirements()` (lines 112–120):

```python
def get_requirements(self, config: AgentConfig) -> list[str]:
    deps = [
        "langgraph>=0.2.0",
        "langchain-core>=0.3.0",
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.27.0",
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
    ]
    if config.model.primary.startswith("ollama/"):
        deps.append("litellm>=1.40.0")
    return deps
```

Replace the Dockerfile write in `build()` (line 99, `dockerfile.write_text(DOCKERFILE_TEMPLATE)`):

```python
env_block = build_env_block(config, "langgraph")
ollama_extra = ""
if config.model.primary.startswith("ollama/"):
    ollama_extra = '\nENV OLLAMA_BASE_URL="http://agentbreeder-ollama:11434"'
dockerfile_content = (
    DOCKERFILE_TEMPLATE.rstrip()
    + "\n\n# Agent configuration\n"
    + env_block
    + ollama_extra
    + "\n"
)
dockerfile.write_text(dockerfile_content)
```

Also update the `ContainerImage` return to use `dockerfile_content` instead of `DOCKERFILE_TEMPLATE`:

```python
return ContainerImage(
    tag=tag,
    dockerfile_content=dockerfile_content,
    context_dir=build_dir,
)
```

- [ ] **Step 4: Fix `engine/runtimes/openai_agents.py`**

Add `build_env_block` to the import line (currently line 14):

```python
from engine.runtimes.base import ContainerImage, RuntimeBuilder, RuntimeValidationResult, build_env_block
```

Replace `get_requirements()` (lines 114–122):

```python
def get_requirements(self, config: AgentConfig) -> list[str]:
    deps = [
        "openai-agents>=0.1.0",
        "openai>=1.60.0",
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.27.0",
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
    ]
    if config.model.primary.startswith("ollama/"):
        deps.append("litellm>=1.40.0")
    return deps
```

Replace the Dockerfile write in `build()` (line 101, `dockerfile.write_text(DOCKERFILE_TEMPLATE)`):

```python
env_block = build_env_block(config, "openai_agents")
ollama_extra = ""
if config.model.primary.startswith("ollama/"):
    ollama_extra = '\nENV OLLAMA_BASE_URL="http://agentbreeder-ollama:11434"'
dockerfile_content = (
    DOCKERFILE_TEMPLATE.rstrip()
    + "\n\n# Agent configuration\n"
    + env_block
    + ollama_extra
    + "\n"
)
dockerfile.write_text(dockerfile_content)
```

Update the `ContainerImage` return:

```python
return ContainerImage(
    tag=tag,
    dockerfile_content=dockerfile_content,
    context_dir=build_dir,
)
```

- [ ] **Step 5: Fix `engine/runtimes/custom.py`**

Replace `get_requirements()` (lines 146–153):

```python
def get_requirements(self, config: AgentConfig) -> list[str]:
    deps = [
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.27.0",
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
    ]
    if config.model.primary.startswith("ollama/"):
        deps.append("litellm>=1.40.0")
    return deps
```

In `build()`, in the fallback mode branch (after `dockerfile_content = FALLBACK_DOCKERFILE`, line 131), replace:

```python
dockerfile_content = FALLBACK_DOCKERFILE
(build_dir / "Dockerfile").write_text(dockerfile_content)
```

with:

```python
from engine.runtimes.base import build_env_block as _build_env_block  # local import to avoid circular
ollama_extra = ""
if config.model.primary.startswith("ollama/"):
    ollama_extra = '\nENV OLLAMA_BASE_URL="http://agentbreeder-ollama:11434"'
env_block = _build_env_block(config, "custom")
dockerfile_content = (
    FALLBACK_DOCKERFILE.rstrip()
    + "\n\n# Agent configuration\n"
    + env_block
    + ollama_extra
    + "\n"
)
(build_dir / "Dockerfile").write_text(dockerfile_content)
```

Note: `build_env_block` is already imported at the top of `custom.py` if it was added — check the import and use the top-level import if present rather than the local import. The local import shown above is a safe fallback.

- [ ] **Step 6: Run tests to confirm they pass**

```bash
cd /Users/rajit/personal-github/agentbreeder
python3 -m pytest tests/unit/test_runtimes.py -k "ollama" -v
python3 -m pytest tests/unit/test_openai_agents_runtime.py -k "ollama" -v
```

Expected: all new tests `PASSED`.

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
python3 -m pytest tests/unit/test_runtimes.py tests/unit/test_openai_agents_runtime.py tests/unit/test_runtime_custom.py -v
```

Expected: all existing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add engine/runtimes/langgraph.py engine/runtimes/openai_agents.py engine/runtimes/custom.py \
        tests/unit/test_runtimes.py tests/unit/test_openai_agents_runtime.py
git commit -m "feat(runtimes): litellm dep + OLLAMA_BASE_URL env injection for LangGraph, OpenAI Agents, Custom (#63)"
```

---

## Task 2: OpenAI Agents server template — configure Ollama client at startup

**Files:**
- Modify: `engine/runtimes/templates/openai_agents_server.py`

The startup function (lines 81–103) sets `set_default_openai_key` but never configures the base URL. For `ollama/` models, we need to point the OpenAI client at Ollama's OpenAI-compatible endpoint.

- [ ] **Step 1: Write failing test**

In `tests/unit/test_openai_agents_runtime.py`, append:

```python
def test_server_template_handles_ollama_model(self) -> None:
    """Server template must reference OLLAMA_BASE_URL and detect ollama/ prefix."""
    from pathlib import Path
    template = (
        Path(__file__).parent.parent.parent
        / "engine/runtimes/templates/openai_agents_server.py"
    ).read_text()
    assert "OLLAMA_BASE_URL" in template
    assert "ollama/" in template or "startswith" in template
```

- [ ] **Step 2: Run to confirm it fails**

```bash
python3 -m pytest tests/unit/test_openai_agents_runtime.py::TestOpenAIAgentsRuntime::test_server_template_handles_ollama_model -v
```

Expected: `FAILED` — `OLLAMA_BASE_URL` not in template.

- [ ] **Step 3: Update `engine/runtimes/templates/openai_agents_server.py`**

Find the startup function (lines 81–103). Replace the entire `startup` function body with:

```python
@app.on_event("startup")
async def startup() -> None:
    global _agent, _tracer  # noqa: PLW0603
    logger.info("Loading OpenAI Agents SDK agent...")
    _agent = _load_agent()
    logger.info("Agent loaded successfully")

    try:
        from _tracing import init_tracing

        _tracer = init_tracing()
    except ImportError:
        pass

    import os as _os

    agent_model = _os.getenv("AGENT_MODEL", "")

    if agent_model.startswith("ollama/"):
        # Configure OpenAI Agents SDK to use Ollama's OpenAI-compatible endpoint
        from openai import AsyncOpenAI
        from agents import set_default_openai_client

        ollama_base_url = _os.getenv("OLLAMA_BASE_URL", "http://agentbreeder-ollama:11434")
        model_name = agent_model.split("/", 1)[1]  # strip "ollama/" prefix
        ollama_client = AsyncOpenAI(
            base_url=f"{ollama_base_url}/v1",
            api_key="ollama",  # Ollama doesn't require a real key
        )
        set_default_openai_client(ollama_client)
        logger.info(
            "Configured OpenAI Agents SDK to use Ollama: model=%s base_url=%s/v1",
            model_name,
            ollama_base_url,
        )
    else:
        from agents import set_default_openai_key

        api_key = _os.getenv("OPENAI_API_KEY")
        if api_key:
            set_default_openai_key(api_key)
            logger.info("Default OpenAI API key configured")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/unit/test_openai_agents_runtime.py -v
```

Expected: all tests pass including the new one.

- [ ] **Step 5: Commit**

```bash
git add engine/runtimes/templates/openai_agents_server.py tests/unit/test_openai_agents_runtime.py
git commit -m "feat(runtimes): OpenAI Agents server template routes to Ollama when model is ollama/ (#63)"
```

---

## Task 3: CrewAI — litellm dep + server template sets base_url for Ollama

**Files:**
- Modify: `engine/runtimes/crewai.py`
- Modify: `engine/runtimes/templates/crewai_server.py`
- Modify: `tests/unit/test_runtime_crewai.py`

- [ ] **Step 1: Write failing tests**

In `tests/unit/test_runtime_crewai.py`, append after `test_get_requirements_returns_non_empty_list_of_strings`:

```python
def test_get_requirements_adds_litellm_for_ollama_model(self) -> None:
    from engine.runtimes.crewai import CrewAIRuntime

    config = make_agent_config(model_primary="ollama/llama3:8b")
    runtime = CrewAIRuntime()
    reqs = runtime.get_requirements(config)
    assert any("litellm" in r for r in reqs)

def test_get_requirements_no_litellm_for_non_ollama_model(self) -> None:
    from engine.runtimes.crewai import CrewAIRuntime

    config = make_agent_config(model_primary="gpt-4o")
    runtime = CrewAIRuntime()
    reqs = runtime.get_requirements(config)
    assert not any("litellm" in r for r in reqs)
```

Also append a server template check:

```python
def test_server_template_sets_ollama_base_url(self) -> None:
    """CrewAI server template must set agent.llm.base_url for ollama/ models."""
    from pathlib import Path
    template = (
        Path(__file__).parent.parent.parent
        / "engine/runtimes/templates/crewai_server.py"
    ).read_text()
    assert "OLLAMA_BASE_URL" in template
    assert "base_url" in template
```

- [ ] **Step 2: Run to confirm they fail**

```bash
python3 -m pytest tests/unit/test_runtime_crewai.py -k "ollama" -v
```

Expected: `FAILED`.

- [ ] **Step 3: Fix `engine/runtimes/crewai.py` `get_requirements()`**

Replace `get_requirements()` (lines 146–154):

```python
def get_requirements(self, config: AgentConfig) -> list[str]:
    deps = [
        "crewai>=0.80.0",
        "crewai-tools>=0.4.0",
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.27.0",
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
    ]
    if config.model.primary.startswith("ollama/"):
        deps.append("litellm>=1.40.0")
    return deps
```

- [ ] **Step 4: Fix `engine/runtimes/templates/crewai_server.py` startup**

Find the section in startup that sets `agent.llm.model` (lines 189–195):

```python
            if _agent_model and hasattr(agent, "llm") and agent.llm is not None:
                try:
                    agent.llm.model = _agent_model
                    if _agent_temperature is not None:
                        agent.llm.temperature = float(_agent_temperature)
                except Exception:
                    pass
```

Replace with:

```python
            if _agent_model and hasattr(agent, "llm") and agent.llm is not None:
                try:
                    agent.llm.model = _agent_model
                    if _agent_temperature is not None:
                        agent.llm.temperature = float(_agent_temperature)
                    # For Ollama models, set base_url so LiteLLM routes correctly
                    if _agent_model.startswith("ollama/"):
                        _ollama_url = os.getenv(
                            "OLLAMA_BASE_URL", "http://agentbreeder-ollama:11434"
                        )
                        agent.llm.base_url = _ollama_url
                        logger.info("Configured CrewAI agent LLM for Ollama: %s", _ollama_url)
                except Exception:
                    pass
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python3 -m pytest tests/unit/test_runtime_crewai.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add engine/runtimes/crewai.py engine/runtimes/templates/crewai_server.py tests/unit/test_runtime_crewai.py
git commit -m "feat(runtimes): CrewAI adds litellm dep + sets Ollama base_url in server startup (#63)"
```

---

## Task 4: Google ADK — LiteLlm injection in SERVER_LOADER_CONTENT and server template

**Files:**
- Modify: `engine/runtimes/google_adk.py`
- Modify: `engine/runtimes/templates/google_adk_server.py`
- Modify: `tests/unit/test_runtime_google_adk.py`

- [ ] **Step 1: Write failing tests**

In `tests/unit/test_runtime_google_adk.py`, append after `test_get_requirements_includes_core_deps`:

```python
def test_get_requirements_adds_litellm_for_ollama_model(self, tmp_path: Path) -> None:
    from engine.runtimes.google_adk import GoogleADKRuntime

    config = make_agent_config(model_primary="ollama/gemma3:27b")
    runtime = GoogleADKRuntime()
    reqs = runtime.get_requirements(config)
    assert any("litellm" in r for r in reqs)

def test_server_loader_uses_litellm_for_ollama_model(self) -> None:
    """SERVER_LOADER_CONTENT must import and use LiteLlm for ollama/ model strings."""
    from engine.runtimes.google_adk import SERVER_LOADER_CONTENT

    assert "LiteLlm" in SERVER_LOADER_CONTENT or "LiteLlmModel" in SERVER_LOADER_CONTENT
    assert "ollama/" in SERVER_LOADER_CONTENT or "startswith" in SERVER_LOADER_CONTENT

def test_server_template_uses_litellm_for_model_override(self) -> None:
    """google_adk_server.py must use LiteLlm when applying AGENT_MODEL for non-Gemini models."""
    from pathlib import Path
    template = (
        Path(__file__).parent.parent.parent
        / "engine/runtimes/templates/google_adk_server.py"
    ).read_text()
    assert "LiteLlm" in template
    assert "OLLAMA_BASE_URL" in template
```

- [ ] **Step 2: Run to confirm they fail**

```bash
python3 -m pytest tests/unit/test_runtime_google_adk.py -k "litellm or ollama" -v
```

Expected: `FAILED`.

- [ ] **Step 3: Fix `engine/runtimes/google_adk.py` — `get_requirements()`**

In `get_requirements()` (lines 213–224), add the litellm conditional:

```python
def get_requirements(self, config: AgentConfig) -> list[str]:
    deps = [
        "google-adk>=1.29.0",
        "google-generativeai>=0.8.0",
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.27.0",
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
    ]
    # Add GCS dep when artifact_service=gcs
    if config.google_adk and config.google_adk.artifact_service.value == "gcs":
        deps.append("google-cloud-storage>=2.0.0")
    # Add LiteLLM for non-Gemini models (e.g. ollama/)
    if "/" in config.model.primary and not config.model.primary.startswith("gemini"):
        deps.append("litellm>=1.40.0")
    return deps
```

- [ ] **Step 4: Fix `engine/runtimes/google_adk.py` — `SERVER_LOADER_CONTENT` fallback**

In `SERVER_LOADER_CONTENT` (lines 31–67), replace the fallback `Agent()` construction (the block starting at `return Agent(`):

Find this section (approximately lines 56–66):

```python
    return Agent(
        name=data.get("name", "yaml-agent"),
        model=data.get("model", "gemini-2.0-flash"),
        description=data.get("description", ""),
        instruction=data.get("instruction", ""),
    )
```

Replace with:

```python
    raw_model = data.get("model", "gemini-2.0-flash")
    if "/" in raw_model and not raw_model.startswith("gemini"):
        # Non-Gemini model (e.g. ollama/gemma3:27b) — route through LiteLlm
        import os as _os
        from google.adk.models.lite_llm import LiteLlm
        model_arg = LiteLlm(
            model=raw_model,
            api_base=_os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
    else:
        model_arg = raw_model

    return Agent(
        name=data.get("name", "yaml-agent"),
        model=model_arg,
        description=data.get("description", ""),
        instruction=data.get("instruction", ""),
    )
```

Because this string is embedded in the Python source (inside the triple-quoted `SERVER_LOADER_CONTENT`), make sure the replacement is inside the `load_agent_from_yaml` function block in the string — check indentation carefully (4-space indent inside the function).

- [ ] **Step 5: Fix `engine/runtimes/templates/google_adk_server.py` — lifespan model override**

Find the `AGENT_MODEL` override section in the `lifespan` function (lines 216–221):

```python
    if agent_model and hasattr(_agent, "model"):
        try:
            _agent.model = agent_model
            logger.info("Applied AGENT_MODEL override: %s", agent_model)
        except Exception:
            logger.warning("Could not set AGENT_MODEL on agent — proceeding with agent default")
```

Replace with:

```python
    if agent_model and hasattr(_agent, "model"):
        try:
            if "/" in agent_model and not agent_model.startswith("gemini"):
                # Non-Gemini model (e.g. ollama/) — must use LiteLlm bridge
                from google.adk.models.lite_llm import LiteLlm
                ollama_url = os.getenv(
                    "OLLAMA_BASE_URL", "http://agentbreeder-ollama:11434"
                )
                _agent.model = LiteLlm(model=agent_model, api_base=ollama_url)
                logger.info(
                    "Applied LiteLlm model override: model=%s api_base=%s",
                    agent_model,
                    ollama_url,
                )
            else:
                _agent.model = agent_model
                logger.info("Applied AGENT_MODEL override: %s", agent_model)
        except Exception:
            logger.warning("Could not set AGENT_MODEL on agent — proceeding with agent default")
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
python3 -m pytest tests/unit/test_runtime_google_adk.py -v
```

Expected: all tests pass including the new ones.

- [ ] **Step 7: Commit**

```bash
git add engine/runtimes/google_adk.py engine/runtimes/templates/google_adk_server.py \
        tests/unit/test_runtime_google_adk.py
git commit -m "feat(runtimes): Google ADK uses LiteLlm for ollama/ models in SERVER_LOADER_CONTENT and server template (#63 #66)"
```

---

## Task 5: Claude SDK — block ollama/ models in validate()

**Files:**
- Modify: `engine/runtimes/claude_sdk.py`
- Modify: `tests/unit/test_runtime_claude_sdk.py`

- [ ] **Step 1: Write failing test**

Open `tests/unit/test_runtime_claude_sdk.py`. Find the last test in the file. Append:

```python
def test_validate_rejects_ollama_model(self, tmp_path: Path) -> None:
    """Claude SDK only supports Claude models — ollama/ must be rejected at validate()."""
    from engine.runtimes.claude_sdk import ClaudeSDKRuntime

    (tmp_path / "agent.py").write_text("root_agent = None")
    (tmp_path / "requirements.txt").write_text("anthropic-ai-sdk>=0.1.0\n")
    config = make_agent_config(model_primary="ollama/gemma3:27b")
    runtime = ClaudeSDKRuntime()
    result = runtime.validate(tmp_path, config)
    assert not result.valid
    assert any("ollama" in e.lower() or "Claude" in e for e in result.errors)
```

(Check the test file for the fixture helper name — it may be `make_agent_config`, `_make_config`, or similar.)

- [ ] **Step 2: Run to confirm it fails**

```bash
python3 -m pytest tests/unit/test_runtime_claude_sdk.py::test_validate_rejects_ollama_model -v
```

Expected: `FAILED` — validate currently returns valid even for ollama/ models.

- [ ] **Step 3: Fix `engine/runtimes/claude_sdk.py` `validate()`**

Open `engine/runtimes/claude_sdk.py`. Find `validate()`. Near the beginning of the method, after `errors: list[str] = []`, add:

```python
if config.model.primary.startswith("ollama/"):
    errors.append(
        f"Claude SDK only supports Claude (Anthropic) models. "
        f"Received: '{config.model.primary}'. "
        "Switch to a Claude model (e.g. 'claude-sonnet-4') or use a different framework "
        "(langgraph, crewai, openai_agents, google_adk, or custom) for local Ollama models."
    )
    return RuntimeValidationResult(valid=False, errors=errors)
```

Return early so the rest of validate() doesn't run on an obviously incompatible config.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/unit/test_runtime_claude_sdk.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add engine/runtimes/claude_sdk.py tests/unit/test_runtime_claude_sdk.py
git commit -m "fix(runtimes): Claude SDK validate() rejects ollama/ models with clear error (#63)"
```

---

## Task 6: DockerComposeDeployer — Ollama sidecar auto-injection and model pull

**Files:**
- Modify: `engine/deployers/docker_compose.py`
- Modify: `tests/unit/test_docker_compose_deployer.py`

- [ ] **Step 1: Write failing tests**

Open `tests/unit/test_docker_compose_deployer.py`. Find `test_deploy_builds_and_runs_container` (line 79) for reference — it uses `unittest.mock.patch` on `docker.from_env`. Append new tests after the existing deploy tests:

```python
@pytest.mark.asyncio
async def test_deploy_starts_ollama_sidecar_for_ollama_model(self) -> None:
    """When model is ollama/*, deploy() must ensure the Ollama sidecar is running."""
    from unittest.mock import AsyncMock, MagicMock, call, patch

    from engine.deployers.docker_compose import DockerComposeDeployer
    from engine.runtimes.base import ContainerImage

    mock_client = MagicMock()
    mock_client.images.build.return_value = (MagicMock(), [])
    mock_client.containers.get.side_effect = [
        __import__("docker").errors.NotFound("not found"),  # old container not found
        __import__("docker").errors.NotFound("not found"),  # ollama sidecar not found
    ]
    mock_client.containers.run.return_value = MagicMock(id="container-123")
    mock_client.networks.get.side_effect = __import__("docker").errors.NotFound("no net")
    mock_client.networks.create.return_value = MagicMock()

    config = make_agent_config(model_primary="ollama/gemma3:27b")
    image = ContainerImage(tag="test:1.0.0", dockerfile_content="FROM python", context_dir=Path("/tmp"))
    deployer = DockerComposeDeployer()

    with patch("docker.from_env", return_value=mock_client):
        with patch.object(deployer, "_pull_ollama_model", new_callable=AsyncMock) as mock_pull:
            await deployer.deploy(config, image)

    # Ollama sidecar container should have been started
    sidecar_run_calls = [
        c for c in mock_client.containers.run.call_args_list
        if "ollama/ollama" in str(c)
    ]
    assert len(sidecar_run_calls) >= 1, "Ollama sidecar was not started"
    # Model pull should have been called
    mock_pull.assert_called_once_with(mock_client, "gemma3:27b")


@pytest.mark.asyncio
async def test_deploy_injects_ollama_base_url_in_container_env(self) -> None:
    """For ollama/ models, OLLAMA_BASE_URL must be in the agent container's env."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from engine.deployers.docker_compose import DockerComposeDeployer, OLLAMA_CONTAINER_NAME
    from engine.runtimes.base import ContainerImage

    mock_client = MagicMock()
    mock_client.images.build.return_value = (MagicMock(), [])
    mock_client.containers.get.side_effect = __import__("docker").errors.NotFound("not found")
    mock_client.containers.run.return_value = MagicMock(id="cid")
    mock_client.networks.get.side_effect = __import__("docker").errors.NotFound("no net")
    mock_client.networks.create.return_value = MagicMock()

    config = make_agent_config(model_primary="ollama/gemma3:27b")
    image = ContainerImage(tag="test:1.0.0", dockerfile_content="FROM python", context_dir=Path("/tmp"))
    deployer = DockerComposeDeployer()

    with patch("docker.from_env", return_value=mock_client):
        with patch.object(deployer, "_pull_ollama_model", new_callable=AsyncMock):
            await deployer.deploy(config, image)

    # Find the agent container run call (not the Ollama sidecar run)
    agent_run_call = [
        c for c in mock_client.containers.run.call_args_list
        if "ollama/ollama" not in str(c)
    ]
    assert agent_run_call, "Agent container was not started"
    env_arg = agent_run_call[0].kwargs.get("environment", {})
    assert "OLLAMA_BASE_URL" in env_arg
    assert OLLAMA_CONTAINER_NAME in env_arg["OLLAMA_BASE_URL"]


@pytest.mark.asyncio
async def test_deploy_skips_ollama_sidecar_for_non_ollama_model(self) -> None:
    """For non-ollama models, deploy() must NOT start the Ollama sidecar."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from engine.deployers.docker_compose import DockerComposeDeployer
    from engine.runtimes.base import ContainerImage

    mock_client = MagicMock()
    mock_client.images.build.return_value = (MagicMock(), [])
    mock_client.containers.get.side_effect = __import__("docker").errors.NotFound("not found")
    mock_client.containers.run.return_value = MagicMock(id="cid")

    config = make_agent_config(model_primary="claude-sonnet-4")
    image = ContainerImage(tag="test:1.0.0", dockerfile_content="FROM python", context_dir=Path("/tmp"))
    deployer = DockerComposeDeployer()

    with patch("docker.from_env", return_value=mock_client):
        await deployer.deploy(config, image)

    # Only one containers.run call — for the agent, not an Ollama sidecar
    ollama_runs = [
        c for c in mock_client.containers.run.call_args_list
        if "ollama/ollama" in str(c)
    ]
    assert len(ollama_runs) == 0, "Ollama sidecar was incorrectly started for non-Ollama model"
```

- [ ] **Step 2: Run to confirm they fail**

```bash
python3 -m pytest tests/unit/test_docker_compose_deployer.py -k "ollama" -v
```

Expected: `FAILED` — `OLLAMA_CONTAINER_NAME` doesn't exist, sidecar not started.

- [ ] **Step 3: Implement sidecar logic in `engine/deployers/docker_compose.py`**

At the top of the file, add two constants after the existing constants (after line 26, `BASE_PORT = 8080`):

```python
OLLAMA_CONTAINER_NAME = "agentbreeder-ollama"
OLLAMA_NETWORK_NAME = "agentbreeder-net"
```

Add three new methods to `DockerComposeDeployer` (insert before `deploy()`):

```python
async def _ensure_network(self, client: Any) -> None:
    """Create agentbreeder-net bridge network if it doesn't already exist."""
    try:
        import docker
        client.networks.get(OLLAMA_NETWORK_NAME)
    except docker.errors.NotFound:
        client.networks.create(OLLAMA_NETWORK_NAME, driver="bridge")
        logger.info("Created Docker network: %s", OLLAMA_NETWORK_NAME)

async def _ensure_ollama_sidecar(self, client: Any) -> None:
    """Start the Ollama sidecar container if it is not already running."""
    import docker
    try:
        container = client.containers.get(OLLAMA_CONTAINER_NAME)
        if container.status == "running":
            logger.info("Ollama sidecar already running: %s", OLLAMA_CONTAINER_NAME)
            return
        logger.info("Restarting stopped Ollama container: %s", OLLAMA_CONTAINER_NAME)
        container.start()
    except docker.errors.NotFound:
        logger.info("Starting Ollama sidecar container...")
        client.containers.run(
            "ollama/ollama",
            name=OLLAMA_CONTAINER_NAME,
            ports={"11434/tcp": 11434},
            volumes={"ollama_data": {"bind": "/root/.ollama", "mode": "rw"}},
            network=OLLAMA_NETWORK_NAME,
            detach=True,
            remove=False,
        )
        logger.info("Ollama sidecar started: %s", OLLAMA_CONTAINER_NAME)

async def _pull_ollama_model(self, client: Any, model_tag: str) -> None:
    """Pull the Ollama model inside the sidecar via docker exec.

    Args:
        client: Docker SDK client.
        model_tag: Model tag without provider prefix, e.g. 'gemma3:27b'.
    """
    logger.info("Pulling Ollama model: %s (this may take several minutes)", model_tag)
    container = client.containers.get(OLLAMA_CONTAINER_NAME)
    # Wait up to 30 seconds for Ollama to be ready
    for _ in range(30):
        exit_code, _ = container.exec_run(["ollama", "list"])
        if exit_code == 0:
            break
        await asyncio.sleep(1)
    exit_code, output = container.exec_run(["ollama", "pull", model_tag], stream=False)
    if exit_code != 0:
        logger.warning(
            "ollama pull %s exited %d: %s", model_tag, exit_code, output.decode(errors="replace")
        )
    else:
        logger.info("Pulled Ollama model: %s", model_tag)
```

Note: `Any` is not yet imported in `docker_compose.py`. Either add `from typing import Any` at the top or use the existing import if one exists.

- [ ] **Step 4: Wire sidecar into `deploy()`**

In `deploy()`, find the `container_env` dict (lines 106–113). After:

```python
container_env.update(config.deploy.env_vars)
```

Add:

```python
# For ollama/ models: start Ollama sidecar and pull model weights before the agent
if config.model.primary.startswith("ollama/"):
    await self._ensure_network(client)
    await self._ensure_ollama_sidecar(client)
    model_tag = config.model.primary.split("/", 1)[1]  # e.g. "gemma3:27b"
    await self._pull_ollama_model(client, model_tag)
    container_env["OLLAMA_BASE_URL"] = f"http://{OLLAMA_CONTAINER_NAME}:11434"
```

Also update `client.containers.run()` to add `network=OLLAMA_NETWORK_NAME` when using Ollama. Find the `client.containers.run(...)` call (line 117) and change it to:

```python
run_kwargs: dict = {
    "name": container_name,
    "ports": {"8080/tcp": port},
    "environment": container_env,
    "detach": True,
    "remove": False,
}
if config.model.primary.startswith("ollama/"):
    run_kwargs["network"] = OLLAMA_NETWORK_NAME

container = client.containers.run(image.tag, **run_kwargs)
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python3 -m pytest tests/unit/test_docker_compose_deployer.py -v
```

Expected: all tests pass including the new Ollama sidecar tests.

- [ ] **Step 6: Run full suite for regressions**

```bash
python3 -m pytest tests/unit/ -q --tb=short
```

Expected: same pass count as before (3047) plus the new tests.

- [ ] **Step 7: Commit**

```bash
git add engine/deployers/docker_compose.py tests/unit/test_docker_compose_deployer.py
git commit -m "feat(deployer): DockerComposeDeployer auto-starts Ollama sidecar and pulls model for ollama/* agents (#64 #65)"
```

---

## Self-Review

**Spec coverage:**
- [x] #63: All 6 runtimes — LangGraph (Task 1), OpenAI Agents (Tasks 1+2), Custom (Task 1), CrewAI (Task 3), Google ADK (Task 4), Claude SDK (Task 5)
- [x] #64: Ollama sidecar auto-injection — Task 6 `_ensure_ollama_sidecar()`
- [x] #65: Auto-pull model weights — Task 6 `_pull_ollama_model()`
- [x] #66: Google ADK `root_agent.yaml` + LiteLlm injection — Task 4 (SERVER_LOADER_CONTENT + server template)

**Type consistency:** `_ensure_ollama_sidecar` / `_pull_ollama_model` / `_ensure_network` all take `client: Any` and are `async` — consistent across Tasks 6 steps 3–4.

**No placeholders:** All code is complete and runnable.
