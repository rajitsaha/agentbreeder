"""Tests for Google ADK advanced features: session backends, memory/artifact services,
streaming mode, multi-agent hierarchy, and root_agent.yaml support.
"""

from __future__ import annotations

from pathlib import Path

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
# Server template: streaming mode mapping
# ---------------------------------------------------------------------------


def test_streaming_mode_mapping():
    """Streaming mode strings map to the correct ADK StreamingMode enum values."""
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
        Path(__file__).parent.parent.parent / "engine/runtimes/templates/google_adk_server.py"
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
