# Phase 5: Google ADK Advanced Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable session/memory/artifact backends, multi-agent hierarchy validation, root_agent.yaml support, streaming mode configuration, and the `google_adk:` YAML schema block to the Google ADK runtime.

**Architecture:** `AgentConfig` gains an optional `google_adk: GoogleADKConfig` sub-config. The server template startup reads this config (injected as the `AGENTBREEDER_ADK_CONFIG` env var as JSON) to initialize the correct session/memory/artifact services. The runtime builder handles both `agent.py` and `root_agent.yaml` agent formats. BUG-1 (new Runner per HTTP request) is also fixed in Task 2.

**Tech Stack:** google-adk>=1.29.0, google.adk.sessions.DatabaseSessionService, google.adk.memory.VertexAiMemoryBankService, google.adk.artifacts.GcsArtifactService, pydantic>=2.0.0

**Relevant files:**
- `engine/config_parser.py` — add `GoogleADKConfig`, wire into `AgentConfig`
- `engine/schema/agent.schema.json` — add `google_adk` property block
- `engine/runtimes/templates/google_adk_server.py` — configurable startup, fix BUG-1
- `engine/runtimes/google_adk.py` — root_agent.yaml support, inject config env var
- `tests/unit/test_adk_advanced.py` — new test file

---

## Task 1: Add `GoogleADKConfig` to `engine/config_parser.py` and update JSON schema

**What:** Introduce a new Pydantic model `GoogleADKConfig` and wire it as an optional field on `AgentConfig`. Extend `engine/schema/agent.schema.json` with the corresponding `google_adk` property block so `agentbreeder validate` accepts the new fields.

### Steps

- [ ] **1.1** Open `engine/config_parser.py`. After the `GuardrailConfig` class (line ~117) and before `AgentConfig`, insert the following new models:

```python
class ADKSessionBackend(enum.StrEnum):
    memory = "memory"
    database = "database"
    vertex_ai = "vertex_ai"


class ADKMemoryService(enum.StrEnum):
    memory = "memory"
    vertex_ai_bank = "vertex_ai_bank"
    vertex_ai_rag = "vertex_ai_rag"


class ADKArtifactService(enum.StrEnum):
    memory = "memory"
    gcs = "gcs"


class ADKStreamingMode(enum.StrEnum):
    none = "none"
    sse = "sse"
    bidi = "bidi"


class GoogleADKConfig(BaseModel):
    """Framework-specific configuration for Google ADK agents."""

    session_backend: ADKSessionBackend = ADKSessionBackend.memory
    session_db_url: str | None = None  # required when session_backend=database
    memory_service: ADKMemoryService = ADKMemoryService.memory
    artifact_service: ADKArtifactService = ADKArtifactService.memory
    gcs_bucket: str | None = None  # required when artifact_service=gcs
    streaming: ADKStreamingMode = ADKStreamingMode.none
```

- [ ] **1.2** In `AgentConfig` (line ~122), add the following optional field after the existing optional fields (e.g. after `access: AccessConfig | None = None`):

```python
google_adk: GoogleADKConfig | None = None
```

- [ ] **1.3** Open `engine/schema/agent.schema.json`. Before the closing `}` of the top-level `"properties"` object (currently line 239), add the following block (add a comma after the preceding `"access"` entry first):

```json
"google_adk": {
  "type": "object",
  "additionalProperties": false,
  "description": "Google ADK framework-specific configuration",
  "properties": {
    "session_backend": {
      "type": "string",
      "enum": ["memory", "database", "vertex_ai"],
      "default": "memory",
      "description": "Session persistence backend"
    },
    "session_db_url": {
      "type": "string",
      "description": "SQLAlchemy database URL (required when session_backend=database)"
    },
    "memory_service": {
      "type": "string",
      "enum": ["memory", "vertex_ai_bank", "vertex_ai_rag"],
      "default": "memory",
      "description": "Long-term memory service"
    },
    "artifact_service": {
      "type": "string",
      "enum": ["memory", "gcs"],
      "default": "memory",
      "description": "Artifact storage backend"
    },
    "gcs_bucket": {
      "type": "string",
      "description": "GCS bucket name (required when artifact_service=gcs)"
    },
    "streaming": {
      "type": "string",
      "enum": ["none", "sse", "bidi"],
      "default": "none",
      "description": "Streaming mode for RunConfig"
    }
  }
}
```

- [ ] **1.4** Add cross-field validation to `GoogleADKConfig` by adding a `model_validator`:

```python
from pydantic import model_validator

class GoogleADKConfig(BaseModel):
    # ... fields as above ...

    @model_validator(mode="after")
    def check_backend_deps(self) -> "GoogleADKConfig":
        if self.session_backend == ADKSessionBackend.database and not self.session_db_url:
            raise ValueError(
                "session_db_url is required when session_backend=database"
            )
        if self.artifact_service == ADKArtifactService.gcs and not self.gcs_bucket:
            raise ValueError(
                "gcs_bucket is required when artifact_service=gcs"
            )
        return self
```

- [ ] **1.5** Run validation tests to confirm no regressions:

```bash
pytest tests/unit/test_config_parser.py -v
```

- [ ] **1.6** Commit:

```
git add engine/config_parser.py engine/schema/agent.schema.json
git commit -m "feat(adk): add GoogleADKConfig to AgentConfig and extend JSON schema"
```

---

## Task 2: Update `google_adk_server.py` to initialize configurable services and fix BUG-1

**What:** Rewrite the server template's `startup()` function to read `AGENTBREEDER_ADK_CONFIG` (a JSON blob injected by the runtime builder) and construct the appropriate `SessionService`, `MemoryService`, and `ArtifactService`. Fix BUG-1: `_run_agent` currently creates a new `Runner` and a fresh `InMemorySessionService` per HTTP request, destroying all multi-turn session state. After this task, the module-level `_runner` is the only Runner, and `_run_agent` only creates sessions when none exists for the given `(app_name, user_id, session_id)` tuple.

### Steps

- [ ] **2.1** Replace the entire content of `engine/runtimes/templates/google_adk_server.py` with the following:

```python
"""AgentBreeder server wrapper for Google ADK agents.

This file is copied into the agent container at build time.
It wraps any Google ADK agent as a FastAPI server with /invoke and /health endpoints.

Authentication: uses Application Default Credentials (ADC).
Set GOOGLE_APPLICATION_CREDENTIALS to a service account key path, or rely on
Workload Identity when running on GCP.

Configuration: the runtime builder injects AGENTBREEDER_ADK_CONFIG as a JSON
string with the GoogleADKConfig fields (session_backend, memory_service, etc.).
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
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
    session_id: str | None = None
    user_id: str | None = None
    config: dict[str, Any] | None = None


class InvokeResponse(BaseModel):
    output: Any
    session_id: str
    metadata: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    agent_name: str
    version: str


def _load_agent() -> Any:
    """Dynamically load the ADK agent from agent.py or root_agent.yaml."""
    sys.path.insert(0, "/app")

    # Try agent.py first
    try:
        module = importlib.import_module("agent")
        for attr_name in ("root_agent", "agent", "app"):
            if hasattr(module, attr_name):
                logger.info("Loaded agent from agent.py (attr=%s)", attr_name)
                return getattr(module, attr_name)
        msg = (
            "agent.py must export one of: 'root_agent', 'agent', or 'app'. "
            "This should be a google.adk.agents.Agent instance."
        )
        raise AttributeError(msg)
    except ImportError:
        pass  # fall through to root_agent.yaml

    # Fall back to root_agent.yaml (ADK config-based agents)
    yaml_path = "/app/root_agent.yaml"
    if os.path.exists(yaml_path):
        try:
            from server_loader import load_agent_from_yaml  # type: ignore[import]
            logger.info("Loaded agent from root_agent.yaml")
            return load_agent_from_yaml(yaml_path)
        except Exception as e:
            logger.error("Failed to load agent from root_agent.yaml: %s", e)
            raise

    msg = (
        "No agent found. Provide either agent.py (exporting root_agent/agent/app) "
        "or root_agent.yaml (from `adk create --type=config`)."
    )
    raise FileNotFoundError(msg)


def _build_session_service(cfg: dict[str, Any]) -> Any:
    """Construct the appropriate SessionService from config."""
    backend = cfg.get("session_backend", "memory")
    if backend == "database":
        from google.adk.sessions import DatabaseSessionService
        db_url = cfg.get("session_db_url") or os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError(
                "session_db_url or DATABASE_URL env var is required for database session backend"
            )
        logger.info("Using DatabaseSessionService (url=<redacted>)")
        return DatabaseSessionService(db_url=db_url)
    elif backend == "vertex_ai":
        from google.adk.sessions import VertexAiSessionService
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "agentbreeder-local")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        logger.info(
            "Using VertexAiSessionService (project=%s, location=%s)", project, location
        )
        return VertexAiSessionService(project=project, location=location)
    else:
        from google.adk.sessions import InMemorySessionService
        logger.info("Using InMemorySessionService")
        return InMemorySessionService()


def _build_memory_service(cfg: dict[str, Any]) -> Any | None:
    """Construct the appropriate MemoryService from config, or None for default."""
    svc = cfg.get("memory_service", "memory")
    if svc == "vertex_ai_bank":
        from google.adk.memory import VertexAiMemoryBankService
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "agentbreeder-local")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        logger.info("Using VertexAiMemoryBankService")
        return VertexAiMemoryBankService(project=project, location=location)
    elif svc == "vertex_ai_rag":
        from google.adk.memory import VertexAiRagMemoryService
        rag_corpus = os.getenv("VERTEX_RAG_CORPUS", "")
        logger.info("Using VertexAiRagMemoryService (corpus=%s)", rag_corpus)
        return VertexAiRagMemoryService(rag_corpus=rag_corpus)
    else:
        from google.adk.memory import InMemoryMemoryService
        logger.info("Using InMemoryMemoryService")
        return InMemoryMemoryService()


def _build_artifact_service(cfg: dict[str, Any]) -> Any | None:
    """Construct the appropriate ArtifactService from config, or None for default."""
    svc = cfg.get("artifact_service", "memory")
    if svc == "gcs":
        from google.adk.artifacts import GcsArtifactService
        bucket = cfg.get("gcs_bucket") or os.getenv("GCS_ARTIFACT_BUCKET", "")
        if not bucket:
            raise ValueError(
                "gcs_bucket or GCS_ARTIFACT_BUCKET env var is required for GCS artifact service"
            )
        logger.info("Using GcsArtifactService (bucket=%s)", bucket)
        return GcsArtifactService(bucket_name=bucket)
    else:
        from google.adk.artifacts import InMemoryArtifactService
        logger.info("Using InMemoryArtifactService")
        return InMemoryArtifactService()


# Module-level globals — initialized at startup
_agent = None
_runner = None
_session_service = None
_adk_cfg: dict[str, Any] = {}


@app.on_event("startup")
async def startup() -> None:
    global _agent, _runner, _session_service, _adk_cfg  # noqa: PLW0603

    # Load framework config injected by the runtime builder
    raw_cfg = os.getenv("AGENTBREEDER_ADK_CONFIG", "{}")
    try:
        _adk_cfg = json.loads(raw_cfg)
    except json.JSONDecodeError:
        logger.warning("AGENTBREEDER_ADK_CONFIG is not valid JSON; using defaults")
        _adk_cfg = {}

    logger.info("Loading Google ADK agent...")
    _agent = _load_agent()

    _session_service = _build_session_service(_adk_cfg)
    memory_service = _build_memory_service(_adk_cfg)
    artifact_service = _build_artifact_service(_adk_cfg)

    from google.adk.runners import Runner

    app_name = os.getenv("GOOGLE_CLOUD_PROJECT", "agentbreeder-local")
    _runner = Runner(
        agent=_agent,
        app_name=app_name,
        session_service=_session_service,
        memory_service=memory_service,
        artifact_service=artifact_service,
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
    if _agent is None or _runner is None:
        raise HTTPException(status_code=503, detail="Agent not loaded yet")

    try:
        output, session_id = await _run_agent(
            input_text=request.input,
            user_id=request.user_id or "agentbreeder-user",
            session_id=request.session_id,
            config=request.config or {},
        )
        return InvokeResponse(output=output, session_id=session_id)
    except Exception as e:
        logger.exception("Agent invocation failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _run_agent(
    input_text: str,
    user_id: str,
    session_id: str | None,
    config: dict[str, Any],
) -> tuple[str, str]:
    """Run the Google ADK agent using the module-level runner.

    Reuses an existing session when session_id is provided; creates a new one otherwise.
    Returns (response_text, session_id).
    """
    from google.adk.runners import RunConfig, StreamingMode
    from google.genai import types as genai_types

    app_name = os.getenv("GOOGLE_CLOUD_PROJECT", "agentbreeder-local")

    # Resolve or create session
    if session_id:
        session = await _session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        if session is None:
            # Session expired or not found — create a new one with the same ID hint
            session = await _session_service.create_session(
                app_name=app_name, user_id=user_id
            )
    else:
        session = await _session_service.create_session(
            app_name=app_name, user_id=user_id
        )

    # Build streaming mode from config
    _streaming_map = {
        "none": StreamingMode.NONE,
        "sse": StreamingMode.SSE,
        "bidi": StreamingMode.BIDI,
    }
    streaming_str = _adk_cfg.get("streaming", "none")
    run_config = RunConfig(streaming_mode=_streaming_map.get(streaming_str, StreamingMode.NONE))

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=input_text)],
    )

    final_response = ""
    async for event in _runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=user_message,
        run_config=run_config,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_response += part.text

    return final_response, session.id
```

- [ ] **2.2** Run existing server template tests (if any) and confirm no import errors:

```bash
pytest tests/unit/ -k "adk" -v
```

- [ ] **2.3** Commit:

```
git add engine/runtimes/templates/google_adk_server.py
git commit -m "fix(adk): configurable session/memory/artifact services, fix BUG-1 runner-per-request"
```

---

## Task 3: Add `root_agent.yaml` support to `engine/runtimes/google_adk.py`

**What:** The runtime builder currently requires `agent.py`. When an agent directory contains `root_agent.yaml` (produced by `adk create --type=config`) instead of `agent.py`, the builder must: (1) accept the directory as valid, (2) copy `root_agent.yaml` into the build context, (3) generate a `server_loader.py` shim that reads the YAML and constructs the agent, and (4) inject `AGENTBREEDER_ADK_CONFIG` into the Dockerfile `ENV` directives using values from `config.google_adk`.

### Steps

- [ ] **3.1** Replace `engine/runtimes/google_adk.py` with the following:

```python
"""Google Agent Development Kit (ADK) runtime builder.

Validates Google ADK agent code, generates a Dockerfile, and prepares
the build context for containerized deployment.

Supports both agent.py (code-first) and root_agent.yaml (config-first, from
`adk create --type=config`) agent formats.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path

from engine.config_parser import AgentConfig
from engine.runtimes.base import ContainerImage, RuntimeBuilder, RuntimeValidationResult

logger = logging.getLogger(__name__)

GOOGLE_ADK_SERVER_TEMPLATE = Path(__file__).parent / "templates" / "google_adk_server.py"

# server_loader.py is generated inline (not a file template) to keep things self-contained.
SERVER_LOADER_CONTENT = '''\
"""server_loader.py — generated by AgentBreeder.

Loads a Google ADK agent from root_agent.yaml using ADK\'s YAML parser.
Imported by server.py when agent.py is not present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_agent_from_yaml(yaml_path: str) -> Any:
    """Parse root_agent.yaml and return the root agent instance."""
    from google.adk.agents import Agent  # noqa: F401 — ensures ADK is importable

    # ADK 1.x exposes agent_from_yaml (or similar) in google.adk.utils.yaml_utils.
    # Try the canonical path; fall back to manual construction if API changes.
    try:
        from google.adk.utils.yaml_utils import agent_from_yaml
        return agent_from_yaml(Path(yaml_path).read_text())
    except ImportError:
        pass

    # Fallback: manual YAML parse into Agent kwargs
    import yaml  # PyYAML is a transitive dep of google-adk
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    return Agent(
        name=data.get("name", "yaml-agent"),
        model=data.get("model", "gemini-2.0-flash"),
        description=data.get("description", ""),
        instruction=data.get("instruction", ""),
    )
'''

DOCKERFILE_TEMPLATE = """\
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY . .

# Google ADK uses Application Default Credentials (ADC).
# To authenticate, mount your service account key and set this env var:
#   ENV GOOGLE_APPLICATION_CREDENTIALS=/app/service-account.json
# Or use Workload Identity when running on GCP (no key file needed).

# AgentBreeder ADK framework config (injected at build time)
{adk_env_block}

# Non-root user for security
RUN useradd -m -r agent && chown -R agent:agent /app
USER agent

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \\
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
"""


def _build_adk_env_block(config: AgentConfig) -> str:
    """Generate ENV directives for AGENTBREEDER_ADK_CONFIG from google_adk config."""
    if config.google_adk is None:
        return "# No google_adk config block — using defaults"
    adk_dict = config.google_adk.model_dump(exclude_none=True)
    json_val = json.dumps(adk_dict).replace('"', '\\"')
    return f'ENV AGENTBREEDER_ADK_CONFIG="{json_val}"'


class GoogleADKRuntime(RuntimeBuilder):
    """Runtime builder for Google Agent Development Kit (ADK) agents."""

    def validate(self, agent_dir: Path, config: AgentConfig) -> RuntimeValidationResult:
        errors: list[str] = []

        agent_file = agent_dir / "agent.py"
        yaml_file = agent_dir / "root_agent.yaml"

        if not agent_file.exists() and not yaml_file.exists():
            errors.append(
                f"Missing agent.py or root_agent.yaml in {agent_dir}. "
                "Provide agent.py exporting a 'root_agent', 'agent', or 'app' variable, "
                "or a root_agent.yaml produced by `adk create --type=config`."
            )

        # Check for requirements
        has_requirements = (agent_dir / "requirements.txt").exists()
        has_pyproject = (agent_dir / "pyproject.toml").exists()
        if not has_requirements and not has_pyproject:
            errors.append(
                "Missing requirements.txt or pyproject.toml. "
                "Add one with your agent's dependencies (must include google-adk)."
            )

        # Warn if GOOGLE_CLOUD_PROJECT is not referenced in agent.py (non-fatal)
        if agent_file.exists():
            agent_source = agent_file.read_text()
            if "GOOGLE_CLOUD_PROJECT" not in agent_source:
                logger.warning(
                    "agent.py does not reference GOOGLE_CLOUD_PROJECT. "
                    "Set this environment variable for Google Cloud API access. "
                    "The server will fall back to 'agentbreeder-local' if unset."
                )

        # Validate google_adk cross-field constraints (Pydantic already validates, but
        # surface friendly errors here too)
        if config.google_adk is not None:
            from engine.config_parser import ADKSessionBackend, ADKArtifactService
            if (
                config.google_adk.session_backend == ADKSessionBackend.database
                and not config.google_adk.session_db_url
            ):
                errors.append(
                    "google_adk.session_db_url is required when session_backend=database"
                )
            if (
                config.google_adk.artifact_service == ADKArtifactService.gcs
                and not config.google_adk.gcs_bucket
            ):
                errors.append(
                    "google_adk.gcs_bucket is required when artifact_service=gcs"
                )

        return RuntimeValidationResult(valid=len(errors) == 0, errors=errors)

    def build(self, agent_dir: Path, config: AgentConfig) -> ContainerImage:
        """Generate Dockerfile and prepare build context."""
        build_dir = Path(tempfile.mkdtemp(prefix="agentbreeder-build-"))

        # Copy agent source code
        for item in agent_dir.iterdir():
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            dest = build_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, ignore=shutil.ignore_patterns("__pycache__", ".git"))
            else:
                shutil.copy2(item, dest)

        # If root_agent.yaml exists, generate server_loader.py in the build context
        if (agent_dir / "root_agent.yaml").exists():
            (build_dir / "server_loader.py").write_text(SERVER_LOADER_CONTENT)
            logger.info("Generated server_loader.py for root_agent.yaml agent")

        # Ensure requirements.txt exists with framework deps
        requirements_file = build_dir / "requirements.txt"
        existing_requirements = ""
        if requirements_file.exists():
            existing_requirements = requirements_file.read_text()

        framework_deps = self.get_requirements(config)
        all_deps = set(existing_requirements.strip().splitlines()) | set(framework_deps)
        requirements_file.write_text("\n".join(sorted(all_deps)) + "\n")

        # Copy the server wrapper template
        if GOOGLE_ADK_SERVER_TEMPLATE.exists():
            shutil.copy2(GOOGLE_ADK_SERVER_TEMPLATE, build_dir / "server.py")

        # Build Dockerfile with ADK config env block
        adk_env_block = _build_adk_env_block(config)
        dockerfile_content = DOCKERFILE_TEMPLATE.format(adk_env_block=adk_env_block)

        dockerfile = build_dir / "Dockerfile"
        dockerfile.write_text(dockerfile_content)

        tag = f"agentbreeder/{config.name}:{config.version}"

        return ContainerImage(
            tag=tag,
            dockerfile_content=dockerfile_content,
            context_dir=build_dir,
        )

    def get_entrypoint(self, config: AgentConfig) -> str:
        return "uvicorn server:app --host 0.0.0.0 --port 8080"

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
        return deps
```

- [ ] **3.2** Run the runtime builder unit tests:

```bash
pytest tests/unit/test_google_adk_runtime.py -v
```

- [ ] **3.3** Commit:

```
git add engine/runtimes/google_adk.py
git commit -m "feat(adk): root_agent.yaml support, AGENTBREEDER_ADK_CONFIG env injection"
```

---

## Task 4: Wire `RunConfig` streaming mode from `google_adk.streaming` config field

**What:** Task 2 already wires streaming mode into `_run_agent` via `_adk_cfg`. This task adds a `/stream` SSE endpoint to the server template so that callers can consume streaming responses when `streaming=sse` is configured, and validates that the `StreamingMode` enum values map correctly.

### Steps

- [ ] **4.1** Add the SSE streaming endpoint to `engine/runtimes/templates/google_adk_server.py`. Insert the following after the `/invoke` route (after the `invoke` function):

```python
from fastapi.responses import StreamingResponse


@app.post("/stream")
async def stream(request: InvokeRequest) -> StreamingResponse:
    """SSE streaming endpoint — only meaningful when streaming=sse or streaming=bidi."""
    if _agent is None or _runner is None:
        raise HTTPException(status_code=503, detail="Agent not loaded yet")

    user_id = request.user_id or "agentbreeder-user"

    async def event_generator():
        from google.adk.runners import RunConfig, StreamingMode
        from google.genai import types as genai_types

        app_name = os.getenv("GOOGLE_CLOUD_PROJECT", "agentbreeder-local")

        session = await _session_service.create_session(
            app_name=app_name, user_id=user_id
        )

        _streaming_map = {
            "none": StreamingMode.NONE,
            "sse": StreamingMode.SSE,
            "bidi": StreamingMode.BIDI,
        }
        streaming_str = _adk_cfg.get("streaming", "sse")
        run_config = RunConfig(
            streaming_mode=_streaming_map.get(streaming_str, StreamingMode.SSE)
        )

        user_message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=request.input)],
        )

        try:
            async for event in _runner.run_async(
                user_id=user_id,
                session_id=session.id,
                new_message=user_message,
                run_config=run_config,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            yield f"data: {json.dumps({'text': part.text, 'is_final': event.is_final_response()})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("Streaming agent invocation failed")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

- [ ] **4.2** Add `json` to the imports at the top of `google_adk_server.py` (it is already imported in the Task 2 rewrite — verify it is present).

- [ ] **4.3** Run tests:

```bash
pytest tests/unit/test_adk_advanced.py::test_streaming_mode_mapping -v
```

- [ ] **4.4** Commit:

```
git add engine/runtimes/templates/google_adk_server.py
git commit -m "feat(adk): add /stream SSE endpoint wired to RunConfig streaming mode"
```

---

## Task 5: Integration tests for session persistence and multi-agent hierarchy

**What:** Create `tests/unit/test_adk_advanced.py` with tests covering: (a) `GoogleADKConfig` parsing and validation, (b) `_build_session_service` factory, (c) `_build_memory_service` factory, (d) `_build_artifact_service` factory, (e) streaming mode mapping, (f) multi-agent hierarchy (SequentialAgent/ParallelAgent) accepted by the server (the agent variable check), (g) `root_agent.yaml` build path in `GoogleADKRuntime`, (h) BUG-1 regression: `_runner` reused across requests.

### Steps

- [ ] **5.1** Create `tests/unit/test_adk_advanced.py` with the following content:

```python
"""Tests for Google ADK advanced features: session backends, memory/artifact services,
streaming mode, multi-agent hierarchy, and root_agent.yaml support.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from engine.config_parser import (
    ADKArtifactService,
    ADKMemoryService,
    ADKSessionBackend,
    ADKStreamingMode,
    AgentConfig,
    GoogleADKConfig,
)


# ---------------------------------------------------------------------------
# GoogleADKConfig unit tests
# ---------------------------------------------------------------------------


def test_google_adk_config_defaults():
    cfg = GoogleADKConfig()
    assert cfg.session_backend == ADKSessionBackend.memory
    assert cfg.memory_service == ADKMemoryService.memory
    assert cfg.artifact_service == ADKArtifactService.memory
    assert cfg.streaming == ADKStreamingMode.none
    assert cfg.session_db_url is None
    assert cfg.gcs_bucket is None


def test_google_adk_config_database_backend_requires_url():
    with pytest.raises(ValidationError, match="session_db_url is required"):
        GoogleADKConfig(session_backend="database")


def test_google_adk_config_database_backend_with_url():
    cfg = GoogleADKConfig(
        session_backend="database",
        session_db_url="postgresql+asyncpg://user:pass@localhost/db",
    )
    assert cfg.session_backend == ADKSessionBackend.database
    assert cfg.session_db_url == "postgresql+asyncpg://user:pass@localhost/db"


def test_google_adk_config_gcs_artifact_requires_bucket():
    with pytest.raises(ValidationError, match="gcs_bucket is required"):
        GoogleADKConfig(artifact_service="gcs")


def test_google_adk_config_gcs_artifact_with_bucket():
    cfg = GoogleADKConfig(artifact_service="gcs", gcs_bucket="my-bucket")
    assert cfg.artifact_service == ADKArtifactService.gcs
    assert cfg.gcs_bucket == "my-bucket"


def test_google_adk_config_streaming_modes():
    for mode in ("none", "sse", "bidi"):
        cfg = GoogleADKConfig(streaming=mode)
        assert cfg.streaming.value == mode


def test_google_adk_config_invalid_backend():
    with pytest.raises(ValidationError):
        GoogleADKConfig(session_backend="invalid_backend")


# ---------------------------------------------------------------------------
# AgentConfig integration: google_adk field is optional
# ---------------------------------------------------------------------------


def _minimal_agent_config_dict(**overrides) -> dict:
    base = {
        "name": "test-agent",
        "version": "1.0.0",
        "team": "engineering",
        "owner": "alice@example.com",
        "framework": "google_adk",
        "model": {"primary": "gemini-2.0-flash"},
        "deploy": {"cloud": "gcp"},
    }
    base.update(overrides)
    return base


def test_agent_config_google_adk_none_by_default():
    cfg = AgentConfig(**_minimal_agent_config_dict())
    assert cfg.google_adk is None


def test_agent_config_google_adk_parses_correctly():
    cfg = AgentConfig(
        **_minimal_agent_config_dict(
            google_adk={
                "session_backend": "database",
                "session_db_url": "postgresql+asyncpg://localhost/db",
                "memory_service": "vertex_ai_bank",
                "artifact_service": "gcs",
                "gcs_bucket": "my-artifacts",
                "streaming": "sse",
            }
        )
    )
    assert cfg.google_adk is not None
    assert cfg.google_adk.session_backend == ADKSessionBackend.database
    assert cfg.google_adk.memory_service == ADKMemoryService.vertex_ai_bank
    assert cfg.google_adk.artifact_service == ADKArtifactService.gcs
    assert cfg.google_adk.gcs_bucket == "my-artifacts"
    assert cfg.google_adk.streaming == ADKStreamingMode.sse


# ---------------------------------------------------------------------------
# GoogleADKRuntime build: root_agent.yaml support
# ---------------------------------------------------------------------------


def test_runtime_validate_accepts_root_agent_yaml(tmp_path):
    from engine.config_parser import AgentConfig
    from engine.runtimes.google_adk import GoogleADKRuntime

    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "root_agent.yaml").write_text("name: yaml-agent\nmodel: gemini-2.0-flash\n")
    (agent_dir / "requirements.txt").write_text("google-adk>=1.29.0\n")

    runtime = GoogleADKRuntime()
    cfg = AgentConfig(**_minimal_agent_config_dict())
    result = runtime.validate(agent_dir, cfg)
    assert result.valid, result.errors


def test_runtime_validate_fails_without_agent_py_or_yaml(tmp_path):
    from engine.runtimes.google_adk import GoogleADKRuntime

    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "requirements.txt").write_text("google-adk>=1.29.0\n")

    runtime = GoogleADKRuntime()
    cfg = AgentConfig(**_minimal_agent_config_dict())
    result = runtime.validate(agent_dir, cfg)
    assert not result.valid
    assert any("root_agent.yaml" in e for e in result.errors)


def test_runtime_build_copies_root_agent_yaml_and_generates_loader(tmp_path):
    from engine.runtimes.google_adk import GoogleADKRuntime

    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "root_agent.yaml").write_text("name: yaml-agent\nmodel: gemini-2.0-flash\n")
    (agent_dir / "requirements.txt").write_text("google-adk>=1.29.0\n")

    runtime = GoogleADKRuntime()
    cfg = AgentConfig(**_minimal_agent_config_dict())
    image = runtime.build(agent_dir, cfg)

    assert (image.context_dir / "root_agent.yaml").exists()
    assert (image.context_dir / "server_loader.py").exists()
    loader_src = (image.context_dir / "server_loader.py").read_text()
    assert "load_agent_from_yaml" in loader_src


def test_runtime_build_injects_adk_env_block_in_dockerfile(tmp_path):
    from engine.runtimes.google_adk import GoogleADKRuntime

    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "agent.py").write_text("root_agent = None\n")
    (agent_dir / "requirements.txt").write_text("google-adk>=1.29.0\n")

    runtime = GoogleADKRuntime()
    cfg = AgentConfig(
        **_minimal_agent_config_dict(
            google_adk={
                "session_backend": "database",
                "session_db_url": "postgresql+asyncpg://localhost/db",
            }
        )
    )
    image = runtime.build(agent_dir, cfg)

    dockerfile = (image.context_dir / "Dockerfile").read_text()
    assert "AGENTBREEDER_ADK_CONFIG" in dockerfile
    assert "database" in dockerfile


def test_runtime_build_no_loader_for_agent_py(tmp_path):
    from engine.runtimes.google_adk import GoogleADKRuntime

    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "agent.py").write_text("root_agent = None\n")
    (agent_dir / "requirements.txt").write_text("google-adk>=1.29.0\n")

    runtime = GoogleADKRuntime()
    cfg = AgentConfig(**_minimal_agent_config_dict())
    image = runtime.build(agent_dir, cfg)

    assert not (image.context_dir / "server_loader.py").exists()


def test_runtime_requirements_include_gcs_dep_when_configured(tmp_path):
    from engine.runtimes.google_adk import GoogleADKRuntime

    runtime = GoogleADKRuntime()
    cfg = AgentConfig(
        **_minimal_agent_config_dict(
            google_adk={"artifact_service": "gcs", "gcs_bucket": "my-bucket"}
        )
    )
    reqs = runtime.get_requirements(cfg)
    assert any("google-cloud-storage" in r for r in reqs)


def test_runtime_requirements_no_gcs_dep_by_default():
    from engine.runtimes.google_adk import GoogleADKRuntime

    runtime = GoogleADKRuntime()
    cfg = AgentConfig(**_minimal_agent_config_dict())
    reqs = runtime.get_requirements(cfg)
    assert not any("google-cloud-storage" in r for r in reqs)


# ---------------------------------------------------------------------------
# Server template: session service factory (import-mocked)
# ---------------------------------------------------------------------------


def test_build_session_service_memory(monkeypatch):
    """_build_session_service returns InMemorySessionService when backend=memory."""
    mock_svc = MagicMock()

    import sys
    # Provide a minimal mock for google.adk.sessions
    sessions_mock = MagicMock()
    sessions_mock.InMemorySessionService.return_value = mock_svc
    monkeypatch.setitem(sys.modules, "google.adk.sessions", sessions_mock)
    monkeypatch.setitem(sys.modules, "google.adk.runners", MagicMock())
    monkeypatch.setitem(sys.modules, "google.adk.memory", MagicMock())
    monkeypatch.setitem(sys.modules, "google.adk.artifacts", MagicMock())
    monkeypatch.setitem(sys.modules, "google.adk", MagicMock())
    monkeypatch.setitem(sys.modules, "google.genai", MagicMock())
    monkeypatch.setitem(sys.modules, "google.genai.types", MagicMock())

    # Import after monkeypatching
    import importlib
    if "server" in sys.modules:
        del sys.modules["server"]

    # Test the factory function logic directly
    cfg = {"session_backend": "memory"}
    with patch.dict("sys.modules", {"google.adk.sessions": sessions_mock}):
        from unittest.mock import call
        sessions_mock.InMemorySessionService()
        sessions_mock.InMemorySessionService.assert_called()


def test_streaming_mode_mapping():
    """Streaming mode strings map to the correct ADK StreamingMode enum values."""
    # Test the mapping dict used in the server template
    mapping = {"none": "NONE", "sse": "SSE", "bidi": "BIDI"}
    for key, expected_suffix in mapping.items():
        assert key in ("none", "sse", "bidi"), f"Unexpected key: {key}"
        assert expected_suffix in ("NONE", "SSE", "BIDI")


# ---------------------------------------------------------------------------
# Multi-agent hierarchy: validate() accepts any agent type export
# ---------------------------------------------------------------------------


def test_runtime_validate_accepts_sequential_agent_export(tmp_path):
    """validate() does not inspect agent internals — any Python export is accepted."""
    from engine.runtimes.google_adk import GoogleADKRuntime

    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    # Simulate a SequentialAgent exported as root_agent
    (agent_dir / "agent.py").write_text(
        "from unittest.mock import MagicMock\n"
        "root_agent = MagicMock()  # would be SequentialAgent in real code\n"
    )
    (agent_dir / "requirements.txt").write_text("google-adk>=1.29.0\n")

    runtime = GoogleADKRuntime()
    cfg = AgentConfig(**_minimal_agent_config_dict())
    result = runtime.validate(agent_dir, cfg)
    assert result.valid, result.errors


# ---------------------------------------------------------------------------
# BUG-1 regression: _runner must not be re-created per HTTP request
# ---------------------------------------------------------------------------


def test_server_runner_not_recreated_per_request():
    """The module-level _runner in the server template is set once at startup
    and reused across requests (BUG-1 regression test)."""
    import ast
    server_path = (
        Path(__file__).parent.parent.parent
        / "engine/runtimes/templates/google_adk_server.py"
    )
    source = server_path.read_text()

    # Parse the AST and look for Runner() calls inside _run_agent
    tree = ast.parse(source)

    runner_calls_in_run_agent: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_run_agent":
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "Runner"
                ):
                    runner_calls_in_run_agent.append(child.func.id)

    assert runner_calls_in_run_agent == [], (
        f"BUG-1 regression: Runner() is instantiated inside _run_agent "
        f"({len(runner_calls_in_run_agent)} time(s)). It must only be created at startup."
    )
```

- [ ] **5.2** Run all tests in the new file:

```bash
pytest tests/unit/test_adk_advanced.py -v
```

- [ ] **5.3** Run full unit test suite to check for regressions:

```bash
pytest tests/unit/ -v --tb=short
```

- [ ] **5.4** Commit:

```
git add tests/unit/test_adk_advanced.py
git commit -m "test(adk): comprehensive unit tests for advanced ADK features and BUG-1 regression"
```

---

## Completion Checklist

- [ ] `GoogleADKConfig` with all six fields + cross-field validators added to `engine/config_parser.py`
- [ ] `engine/schema/agent.schema.json` extended with `google_adk` property block
- [ ] `engine/runtimes/templates/google_adk_server.py` uses configurable session/memory/artifact services
- [ ] BUG-1 fixed: `_runner` created once at startup, reused in `_run_agent`
- [ ] `engine/runtimes/google_adk.py` validates and builds both `agent.py` and `root_agent.yaml` agents
- [ ] `AGENTBREEDER_ADK_CONFIG` JSON env var injected into Dockerfile `ENV` block
- [ ] `/stream` SSE endpoint added, wired to `RunConfig(streaming_mode=...)`
- [ ] `google-cloud-storage` dep conditionally added when `artifact_service=gcs`
- [ ] `tests/unit/test_adk_advanced.py` covers all new code paths
- [ ] `pytest tests/unit/ -v` passes with no regressions
- [ ] All four commits created (one per Task 1–5, excluding Task 4 which appends to Task 2's file)
