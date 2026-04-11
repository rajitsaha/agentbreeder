"""Tests for engine/runtimes/custom.py — Custom (BYO) runtime builder."""

from __future__ import annotations

from pathlib import Path

from engine.config_parser import AgentConfig, FrameworkType
from engine.runtimes.custom import CustomRuntime


def _make_config(**overrides) -> AgentConfig:
    defaults = {
        "name": "test-agent",
        "version": "1.0.0",
        "team": "test",
        "owner": "test@example.com",
        "framework": FrameworkType.custom,
        "model": {"primary": "claude-sonnet-4"},
        "deploy": {"cloud": "local"},
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)


def _make_agent_dir(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """Create a temporary agent directory with the given files."""
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    if files:
        for name, content in files.items():
            (agent_dir / name).write_text(content)
    return agent_dir


# ---------------------------------------------------------------------------
# validate() tests
# ---------------------------------------------------------------------------


class TestCustomRuntimeValidate:
    def test_byo_dockerfile_with_port_8080_is_valid(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "Dockerfile": "FROM python:3.11-slim\nEXPOSE 8080\nCMD ['uvicorn', 'app:app']",
                "requirements.txt": "fastapi>=0.110.0",
            },
        )
        runtime = CustomRuntime()
        result = runtime.validate(agent_dir, _make_config())
        assert result.valid is True
        assert result.errors == []

    def test_agent_py_with_requirements_is_valid(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "agent = None",
                "requirements.txt": "my-framework>=1.0",
            },
        )
        runtime = CustomRuntime()
        result = runtime.validate(agent_dir, _make_config())
        assert result.valid is True
        assert result.errors == []

    def test_main_py_with_pyproject_is_valid(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "main.py": "handler = None",
                "pyproject.toml": "[project]\nname='myagent'",
            },
        )
        runtime = CustomRuntime()
        result = runtime.validate(agent_dir, _make_config())
        assert result.valid is True
        assert result.errors == []

    def test_no_entry_point_is_invalid(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {"requirements.txt": "fastapi>=0.110.0"},
        )
        runtime = CustomRuntime()
        result = runtime.validate(agent_dir, _make_config())
        assert result.valid is False
        assert any("Dockerfile" in e or "agent.py" in e or "main.py" in e for e in result.errors)

    def test_missing_requirements_is_invalid(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {"agent.py": "agent = None"},
        )
        runtime = CustomRuntime()
        result = runtime.validate(agent_dir, _make_config())
        assert result.valid is False
        assert any("requirements" in e.lower() for e in result.errors)

    def test_byo_dockerfile_missing_port_8080_warns(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "Dockerfile": "FROM python:3.11-slim\nCMD ['python', 'app.py']",
                "requirements.txt": "fastapi>=0.110.0",
            },
        )
        runtime = CustomRuntime()
        result = runtime.validate(agent_dir, _make_config())
        # Port warning is surfaced as a soft error (invalid)
        assert result.valid is False
        assert any("8080" in e for e in result.errors)

    def test_empty_directory_is_invalid(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runtime = CustomRuntime()
        result = runtime.validate(agent_dir, _make_config())
        assert result.valid is False
        assert len(result.errors) >= 1


# ---------------------------------------------------------------------------
# build() tests — BYO Dockerfile path
# ---------------------------------------------------------------------------


class TestCustomRuntimeBuildWithDockerfile:
    def test_user_dockerfile_is_preserved(self, tmp_path: Path) -> None:
        user_dockerfile = "FROM ubuntu:22.04\nEXPOSE 8080\nCMD ['python', 'app.py']"
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "Dockerfile": user_dockerfile,
                "requirements.txt": "fastapi>=0.110.0",
                "app.py": "print('hello')",
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())

        # The Dockerfile in the build context must be the user's, not the fallback
        built_dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "ubuntu:22.04" in built_dockerfile
        assert "python:3.11-slim" not in built_dockerfile

    def test_user_dockerfile_content_returned_in_image(self, tmp_path: Path) -> None:
        user_dockerfile = "FROM ubuntu:22.04\nEXPOSE 8080"
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "Dockerfile": user_dockerfile,
                "requirements.txt": "fastapi",
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())
        assert "ubuntu:22.04" in image.dockerfile_content

    def test_custom_server_not_injected_when_user_has_dockerfile(self, tmp_path: Path) -> None:
        """When using a BYO Dockerfile, we do NOT inject custom_server.py."""
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "Dockerfile": "FROM ubuntu:22.04\nEXPOSE 8080",
                "requirements.txt": "fastapi",
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())
        # server.py should NOT be present unless the user put one there
        assert not (image.context_dir / "server.py").exists()

    def test_agent_source_files_copied(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "Dockerfile": "FROM ubuntu:22.04\nEXPOSE 8080",
                "requirements.txt": "fastapi",
                "app.py": "# my app",
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())
        assert (image.context_dir / "app.py").exists()

    def test_hidden_files_not_copied(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "Dockerfile": "FROM ubuntu:22.04\nEXPOSE 8080",
                "requirements.txt": "fastapi",
                ".env": "SECRET=password",
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())
        assert not (image.context_dir / ".env").exists()


# ---------------------------------------------------------------------------
# build() tests — fallback Dockerfile path
# ---------------------------------------------------------------------------


class TestCustomRuntimeBuildFallback:
    def test_fallback_dockerfile_written(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "agent = None",
                "requirements.txt": "my-framework>=1.0",
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())

        dockerfile = (image.context_dir / "Dockerfile").read_text()
        assert "FROM python:3.11-slim" in dockerfile
        assert "EXPOSE 8080" in dockerfile
        assert "uvicorn" in dockerfile

    def test_fallback_dockerfile_content_in_image(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "agent = None",
                "requirements.txt": "my-framework>=1.0",
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())
        assert "FROM python:3.11-slim" in image.dockerfile_content

    def test_custom_server_template_injected_when_no_user_server(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "agent = None",
                "requirements.txt": "my-framework>=1.0",
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())

        server_file = image.context_dir / "server.py"
        assert server_file.exists()
        server_content = server_file.read_text()
        assert "FastAPI" in server_content
        assert "/health" in server_content
        assert "/invoke" in server_content

    def test_user_server_py_not_overwritten(self, tmp_path: Path) -> None:
        user_server_content = "# my custom server\napp = None"
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "agent = None",
                "requirements.txt": "my-framework>=1.0",
                "server.py": user_server_content,
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())

        server_content = (image.context_dir / "server.py").read_text()
        assert server_content == user_server_content

    def test_framework_deps_merged_into_requirements(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "agent = None",
                "requirements.txt": "my-framework>=1.0\ncustom-lib==2.3.4",
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())

        reqs = (image.context_dir / "requirements.txt").read_text()
        assert "my-framework>=1.0" in reqs
        assert "custom-lib==2.3.4" in reqs
        assert "fastapi" in reqs.lower()
        assert "uvicorn" in reqs.lower()

    def test_tag_uses_agent_name_and_version(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "agent = None",
                "requirements.txt": "my-framework>=1.0",
            },
        )
        runtime = CustomRuntime()
        config = _make_config(name="my-custom-agent", version="2.3.0")
        image = runtime.build(agent_dir, config)
        assert image.tag == "agentbreeder/my-custom-agent:2.3.0"

    def test_context_dir_exists(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path,
            {
                "agent.py": "agent = None",
                "requirements.txt": "my-framework>=1.0",
            },
        )
        runtime = CustomRuntime()
        image = runtime.build(agent_dir, _make_config())
        assert image.context_dir.exists()
        assert image.context_dir.is_dir()


# ---------------------------------------------------------------------------
# get_entrypoint() and get_requirements() tests
# ---------------------------------------------------------------------------


class TestCustomRuntimeEntrypointAndRequirements:
    def test_get_entrypoint_uses_uvicorn_on_8080(self) -> None:
        runtime = CustomRuntime()
        entrypoint = runtime.get_entrypoint(_make_config())
        assert "uvicorn" in entrypoint
        assert "8080" in entrypoint
        assert "server:app" in entrypoint

    def test_get_requirements_is_minimal(self) -> None:
        runtime = CustomRuntime()
        reqs = runtime.get_requirements(_make_config())
        assert any("fastapi" in r for r in reqs)
        assert any("uvicorn" in r for r in reqs)
        assert any("httpx" in r for r in reqs)
        assert any("pydantic" in r for r in reqs)
        # Must NOT include any framework-specific libraries
        assert not any("langgraph" in r for r in reqs)
        assert not any("crewai" in r for r in reqs)
        assert not any("openai" in r.lower() for r in reqs)

    def test_get_requirements_returns_list_of_strings(self) -> None:
        runtime = CustomRuntime()
        reqs = runtime.get_requirements(_make_config())
        assert isinstance(reqs, list)
        assert all(isinstance(r, str) for r in reqs)
