"""Tests for engine/runtimes/google_adk.py — Google ADK runtime builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.config_parser import AgentConfig, FrameworkType
from engine.runtimes.google_adk import GoogleADKRuntime


def _make_config(**overrides: object) -> AgentConfig:
    defaults: dict[str, object] = {
        "name": "test-agent",
        "version": "1.0.0",
        "team": "test",
        "owner": "test@example.com",
        "framework": FrameworkType.google_adk,
        "model": {"primary": "gemini-2.0-flash"},
        "deploy": {"cloud": "gcp"},
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)


def _make_agent_dir(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """Create a temp directory with agent files using pytest's tmp_path."""
    if files:
        for name, content in files.items():
            (tmp_path / name).write_text(content)
    return tmp_path


class TestGoogleADKRuntimeValidate:
    def test_validate_valid_agent(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "from google.adk.agents import Agent\nroot_agent = Agent(name='t')",
                "requirements.txt": "google-adk>=0.3.0",
            },
        )
        config = _make_config()
        result = runtime.validate(agent_dir, config)
        assert result.valid is True
        assert result.errors == []

    def test_validate_missing_agent_py(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(tmp_path, {"requirements.txt": "google-adk>=0.3.0"})
        config = _make_config()
        result = runtime.validate(agent_dir, config)
        assert result.valid is False
        assert any("agent.py" in e for e in result.errors)

    def test_validate_missing_requirements(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(tmp_path, {"agent.py": "root_agent = None"})
        config = _make_config()
        result = runtime.validate(agent_dir, config)
        assert result.valid is False
        assert any("requirements" in e.lower() for e in result.errors)

    def test_validate_pyproject_accepted(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "root_agent = None",
                "pyproject.toml": "[project]\nname='test'",
            },
        )
        config = _make_config()
        result = runtime.validate(agent_dir, config)
        assert result.valid is True

    def test_validate_multiple_errors_empty_dir(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(tmp_path, {})
        config = _make_config()
        result = runtime.validate(agent_dir, config)
        assert result.valid is False
        assert len(result.errors) == 2  # missing agent.py + missing requirements

    def test_validate_missing_google_cloud_project_is_non_fatal(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing GOOGLE_CLOUD_PROJECT reference should warn but not fail validation."""
        import logging

        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                # agent.py has no GOOGLE_CLOUD_PROJECT reference
                "agent.py": "root_agent = None",
                "requirements.txt": "google-adk>=0.3.0",
            },
        )
        config = _make_config()
        with caplog.at_level(logging.WARNING, logger="engine.runtimes.google_adk"):
            result = runtime.validate(agent_dir, config)
        assert result.valid is True
        assert result.errors == []
        assert any("GOOGLE_CLOUD_PROJECT" in record.message for record in caplog.records)


class TestGoogleADKRuntimeBuild:
    def test_build_creates_container_image(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "root_agent = None",
                "requirements.txt": "google-adk>=0.3.0",
            },
        )
        config = _make_config()
        image = runtime.build(agent_dir, config)
        assert image.tag == "agentbreeder/test-agent:1.0.0"
        assert image.context_dir.exists()
        assert (image.context_dir / "Dockerfile").exists()
        assert (image.context_dir / "requirements.txt").exists()
        assert (image.context_dir / "agent.py").exists()
        assert "FROM python:3.11-slim" in image.dockerfile_content

    def test_build_copies_server_template(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "root_agent = None",
                "requirements.txt": "google-adk>=0.3.0",
            },
        )
        config = _make_config()
        image = runtime.build(agent_dir, config)
        server_file = image.context_dir / "server.py"
        assert server_file.exists()
        server_content = server_file.read_text()
        assert "FastAPI" in server_content
        assert "Google ADK" in server_content

    def test_build_merges_requirements(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "root_agent = None",
                "requirements.txt": "custom-package>=1.0\ngoogle-adk>=0.3.0",
            },
        )
        config = _make_config()
        image = runtime.build(agent_dir, config)
        reqs = (image.context_dir / "requirements.txt").read_text()
        assert "custom-package>=1.0" in reqs
        assert "google-adk" in reqs
        assert "fastapi" in reqs.lower()
        assert "uvicorn" in reqs.lower()

    def test_build_skips_hidden_files(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "root_agent = None",
                "requirements.txt": "google-adk>=0.3.0",
                ".env": "GOOGLE_CLOUD_PROJECT=secret",
            },
        )
        config = _make_config()
        image = runtime.build(agent_dir, config)
        assert not (image.context_dir / ".env").exists()

    def test_build_skips_pycache(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "root_agent = None",
                "requirements.txt": "google-adk>=0.3.0",
            },
        )
        pycache = agent_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "agent.cpython-311.pyc").write_text("bytecode")
        config = _make_config()
        image = runtime.build(agent_dir, config)
        assert not (image.context_dir / "__pycache__").exists()

    def test_build_tag_format(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "root_agent = None",
                "requirements.txt": "google-adk>=0.3.0",
            },
        )
        config = _make_config(name="my-adk-agent", version="3.2.1")
        image = runtime.build(agent_dir, config)
        assert image.tag == "agentbreeder/my-adk-agent:3.2.1"

    def test_dockerfile_contains_adc_comment(self, tmp_path: Path) -> None:
        runtime = GoogleADKRuntime()
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "root_agent = None",
                "requirements.txt": "google-adk>=0.3.0",
            },
        )
        config = _make_config()
        image = runtime.build(agent_dir, config)
        assert "GOOGLE_APPLICATION_CREDENTIALS" in image.dockerfile_content


class TestGoogleADKRuntimeEntrypoint:
    def test_get_entrypoint(self) -> None:
        runtime = GoogleADKRuntime()
        config = _make_config()
        entrypoint = runtime.get_entrypoint(config)
        assert "uvicorn" in entrypoint
        assert "8080" in entrypoint
        assert "server:app" in entrypoint


class TestGoogleADKRuntimeRequirements:
    def test_get_requirements_includes_google_adk(self) -> None:
        runtime = GoogleADKRuntime()
        config = _make_config()
        reqs = runtime.get_requirements(config)
        assert any("google-adk" in r for r in reqs)

    def test_get_requirements_includes_core_deps(self) -> None:
        runtime = GoogleADKRuntime()
        config = _make_config()
        reqs = runtime.get_requirements(config)
        assert any("google-generativeai" in r for r in reqs)
        assert any("fastapi" in r for r in reqs)
        assert any("uvicorn" in r for r in reqs)
        assert any("httpx" in r for r in reqs)
        assert any("pydantic" in r for r in reqs)

    def test_get_requirements_returns_list(self) -> None:
        runtime = GoogleADKRuntime()
        config = _make_config()
        reqs = runtime.get_requirements(config)
        assert isinstance(reqs, list)
        assert len(reqs) > 0
        assert all(isinstance(r, str) for r in reqs)
