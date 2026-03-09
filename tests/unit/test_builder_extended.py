"""Extended tests for engine/builder.py to cover remaining uncovered lines."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.builder import DeployEngine, DeployError
from engine.config_parser import FrameworkType
from engine.deployers.base import DeployResult, HealthStatus, InfraResult
from engine.governance import RBACDeniedError
from engine.runtimes.base import RuntimeValidationResult


def _make_agent_dir() -> Path:
    d = Path(tempfile.mkdtemp())
    (d / "agent.yaml").write_text("""\
name: test-agent
version: 1.0.0
team: test
owner: test@example.com
framework: langgraph
model:
  primary: gpt-4o
deploy:
  cloud: local
""")
    (d / "agent.py").write_text("graph = None")
    (d / "requirements.txt").write_text("langgraph>=0.2.0")
    return d


class TestDeployEngineEdgeCases:
    @pytest.mark.asyncio
    async def test_deploy_fails_on_rbac(self) -> None:
        """RBAC failure should stop pipeline at step 2."""
        agent_dir = _make_agent_dir()

        with patch(
            "engine.builder.check_rbac",
            side_effect=RBACDeniedError("alice", "platform", "deploy"),
        ):
            engine = DeployEngine()
            with pytest.raises(RBACDeniedError):
                await engine.deploy(agent_dir / "agent.yaml")

    @pytest.mark.asyncio
    async def test_deploy_fails_on_resolution(self) -> None:
        """Resolution failure should stop pipeline at step 3."""
        agent_dir = _make_agent_dir()

        with patch(
            "engine.builder.resolve_dependencies",
            side_effect=Exception("ref not found"),
        ):
            engine = DeployEngine()
            with pytest.raises(Exception, match="ref not found"):
                await engine.deploy(agent_dir / "agent.yaml")

    @pytest.mark.asyncio
    async def test_deploy_fails_on_build_validation(self) -> None:
        """Build validation failure should stop pipeline at step 4."""
        agent_dir = _make_agent_dir()

        mock_runtime = MagicMock()
        mock_runtime.validate.return_value = RuntimeValidationResult(
            valid=False, errors=["Missing agent.py"]
        )

        with patch("engine.builder.get_runtime", return_value=mock_runtime):
            engine = DeployEngine()
            with pytest.raises(Exception, match="Validation failed"):
                await engine.deploy(agent_dir / "agent.yaml")

    @pytest.mark.asyncio
    async def test_deploy_fails_on_provision(self) -> None:
        """Provision failure should stop pipeline at step 5."""
        agent_dir = _make_agent_dir()

        mock_deployer = MagicMock()
        mock_deployer.provision = AsyncMock(side_effect=Exception("cloud error"))

        with patch("engine.builder.get_deployer", return_value=mock_deployer):
            engine = DeployEngine()
            with pytest.raises(Exception, match="cloud error"):
                await engine.deploy(agent_dir / "agent.yaml")

    @pytest.mark.asyncio
    async def test_deploy_with_target_override(self) -> None:
        """Target parameter should override deploy.cloud in config."""
        agent_dir = _make_agent_dir()

        mock_deployer = MagicMock()
        mock_deployer.provision = AsyncMock(
            return_value=InfraResult(endpoint_url="http://localhost:8080", resource_ids={})
        )
        mock_deployer.deploy = AsyncMock(
            return_value=DeployResult(
                endpoint_url="http://localhost:8080",
                container_id="abc",
                status="running",
                agent_name="test-agent",
                version="1.0.0",
            )
        )
        mock_deployer.health_check = AsyncMock(
            return_value=HealthStatus(healthy=True, checks={})
        )

        with patch("engine.builder.get_deployer", return_value=mock_deployer), patch(
            "engine.builder.REGISTRY_DIR", agent_dir / "registry"
        ):
            engine = DeployEngine()
            result = await engine.deploy(
                agent_dir / "agent.yaml", target="kubernetes"
            )

        assert result.endpoint_url == "http://localhost:8080"

    @pytest.mark.asyncio
    async def test_deploy_fails_on_registration(self) -> None:
        """Registration failure should stop at step 7."""
        agent_dir = _make_agent_dir()

        mock_deployer = MagicMock()
        mock_deployer.provision = AsyncMock(
            return_value=InfraResult(endpoint_url="http://localhost:8080", resource_ids={})
        )
        mock_deployer.deploy = AsyncMock(
            return_value=DeployResult(
                endpoint_url="http://localhost:8080",
                container_id="abc",
                status="running",
                agent_name="test-agent",
                version="1.0.0",
            )
        )
        mock_deployer.health_check = AsyncMock(
            return_value=HealthStatus(healthy=True, checks={})
        )

        with patch("engine.builder.get_deployer", return_value=mock_deployer), patch(
            "engine.builder.REGISTRY_DIR", Path("/nonexistent/impossible/path")
        ):
            engine = DeployEngine()
            with pytest.raises(Exception):
                await engine.deploy(agent_dir / "agent.yaml")


class TestDeployCommandSuccess:
    """Test the deploy CLI command with a mocked successful deploy."""

    def test_deploy_success_output(self) -> None:
        from typer.testing import CliRunner

        from cli.main import app

        runner = CliRunner()
        agent_dir = _make_agent_dir()

        mock_result = DeployResult(
            endpoint_url="http://localhost:8080",
            container_id="abc123",
            status="running",
            agent_name="test-agent",
            version="1.0.0",
        )

        async def mock_deploy(*args, **kwargs):
            return mock_result

        with patch("cli.commands.deploy.DeployEngine") as MockEngine:
            instance = MockEngine.return_value
            instance.deploy = mock_deploy

            result = runner.invoke(app, ["deploy", str(agent_dir / "agent.yaml")])

        assert result.exit_code == 0
        assert "test-agent" in result.output
        assert "http://localhost:8080" in result.output

    def test_deploy_success_json(self) -> None:
        import json

        from typer.testing import CliRunner

        from cli.main import app

        runner = CliRunner()
        agent_dir = _make_agent_dir()

        mock_result = DeployResult(
            endpoint_url="http://localhost:8080",
            container_id="abc123",
            status="running",
            agent_name="test-agent",
            version="1.0.0",
        )

        async def mock_deploy(*args, **kwargs):
            return mock_result

        with patch("cli.commands.deploy.DeployEngine") as MockEngine:
            instance = MockEngine.return_value
            instance.deploy = mock_deploy

            result = runner.invoke(app, ["deploy", str(agent_dir / "agent.yaml"), "--json"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["agent_name"] == "test-agent"
