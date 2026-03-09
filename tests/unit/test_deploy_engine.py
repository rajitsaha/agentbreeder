"""Tests for engine/builder.py — the deploy pipeline orchestrator."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.builder import DeployEngine, PipelineStep
from engine.config_parser import FrameworkType
from engine.deployers.base import DeployResult, HealthStatus, InfraResult
from engine.runtimes.base import ContainerImage, RuntimeValidationResult


def _make_agent_dir() -> Path:
    """Create a temp agent directory with valid files."""
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


class TestPipelineStep:
    def test_step_lifecycle(self) -> None:
        step = PipelineStep("Test step", 1)
        assert step.status == "pending"
        step.start()
        assert step.status == "running"
        assert step.started_at is not None
        step.complete()
        assert step.status == "completed"
        assert step.completed_at is not None

    def test_step_failure(self) -> None:
        step = PipelineStep("Test step", 1)
        step.start()
        step.fail("something broke")
        assert step.status == "failed"
        assert step.error == "something broke"


class TestDeployEngine:
    @pytest.mark.asyncio
    async def test_deploy_calls_all_steps(self) -> None:
        """Verify all 8 pipeline steps are called in order."""
        agent_dir = _make_agent_dir()
        steps_seen: list[str] = []

        def on_step(step: PipelineStep) -> None:
            if step.status == "completed":
                steps_seen.append(step.name)

        mock_deployer = MagicMock()
        mock_deployer.provision = AsyncMock(
            return_value=InfraResult(endpoint_url="http://localhost:8080", resource_ids={})
        )
        mock_deployer.deploy = AsyncMock(
            return_value=DeployResult(
                endpoint_url="http://localhost:8080",
                container_id="abc123",
                status="running",
                agent_name="test-agent",
                version="1.0.0",
            )
        )
        mock_deployer.health_check = AsyncMock(
            return_value=HealthStatus(healthy=True, checks={"healthy": True})
        )

        with patch("engine.builder.get_deployer", return_value=mock_deployer), patch(
            "engine.builder.REGISTRY_DIR", agent_dir / "registry"
        ):
            engine = DeployEngine(on_step=on_step)
            result = await engine.deploy(agent_dir / "agent.yaml")

        assert result.endpoint_url == "http://localhost:8080"
        assert result.agent_name == "test-agent"
        assert len(steps_seen) == 8

    @pytest.mark.asyncio
    async def test_deploy_fails_on_invalid_yaml(self) -> None:
        d = Path(tempfile.mkdtemp())
        (d / "agent.yaml").write_text("invalid: yaml: broken")

        engine = DeployEngine()
        with pytest.raises(Exception):
            await engine.deploy(d / "agent.yaml")

    @pytest.mark.asyncio
    async def test_deploy_fails_on_health_check(self) -> None:
        """If health check fails, deployer.teardown is called."""
        agent_dir = _make_agent_dir()

        mock_deployer = MagicMock()
        mock_deployer.provision = AsyncMock(
            return_value=InfraResult(endpoint_url="http://localhost:8080", resource_ids={})
        )
        mock_deployer.deploy = AsyncMock(
            return_value=DeployResult(
                endpoint_url="http://localhost:8080",
                container_id="abc123",
                status="running",
                agent_name="test-agent",
                version="1.0.0",
            )
        )
        mock_deployer.health_check = AsyncMock(
            return_value=HealthStatus(healthy=False, checks={"healthy": False})
        )
        mock_deployer.teardown = AsyncMock()

        with patch("engine.builder.get_deployer", return_value=mock_deployer):
            engine = DeployEngine()
            with pytest.raises(Exception, match="Health check failed"):
                await engine.deploy(agent_dir / "agent.yaml")

        mock_deployer.teardown.assert_called_once_with("test-agent")

    @pytest.mark.asyncio
    async def test_deploy_registers_agent(self) -> None:
        """After successful deploy, agent should be in local registry."""
        agent_dir = _make_agent_dir()
        registry_dir = agent_dir / "registry"

        mock_deployer = MagicMock()
        mock_deployer.provision = AsyncMock(
            return_value=InfraResult(endpoint_url="http://localhost:8080", resource_ids={})
        )
        mock_deployer.deploy = AsyncMock(
            return_value=DeployResult(
                endpoint_url="http://localhost:8080",
                container_id="abc123",
                status="running",
                agent_name="test-agent",
                version="1.0.0",
            )
        )
        mock_deployer.health_check = AsyncMock(
            return_value=HealthStatus(healthy=True, checks={"healthy": True})
        )

        with patch("engine.builder.get_deployer", return_value=mock_deployer), patch(
            "engine.builder.REGISTRY_DIR", registry_dir
        ):
            engine = DeployEngine()
            await engine.deploy(agent_dir / "agent.yaml")

        import json

        registry = json.loads((registry_dir / "agents.json").read_text())
        assert "test-agent" in registry
        assert registry["test-agent"]["endpoint_url"] == "http://localhost:8080"
        assert registry["test-agent"]["framework"] == "langgraph"

    @pytest.mark.asyncio
    async def test_deploy_step_callback(self) -> None:
        """Verify on_step callback is called for each step transition."""
        agent_dir = _make_agent_dir()
        callback_calls: list[tuple[str, str]] = []

        def on_step(step: PipelineStep) -> None:
            callback_calls.append((step.name, step.status))

        mock_deployer = MagicMock()
        mock_deployer.provision = AsyncMock(
            return_value=InfraResult(endpoint_url="http://localhost:8080", resource_ids={})
        )
        mock_deployer.deploy = AsyncMock(
            return_value=DeployResult(
                endpoint_url="http://localhost:8080",
                container_id="abc123",
                status="running",
                agent_name="test-agent",
                version="1.0.0",
            )
        )
        mock_deployer.health_check = AsyncMock(
            return_value=HealthStatus(healthy=True, checks={"healthy": True})
        )

        with patch("engine.builder.get_deployer", return_value=mock_deployer), patch(
            "engine.builder.REGISTRY_DIR", agent_dir / "registry"
        ):
            engine = DeployEngine(on_step=on_step)
            await engine.deploy(agent_dir / "agent.yaml")

        # Each step should have running + completed = 2 calls per step, 8 steps = 16
        assert len(callback_calls) == 16
        # Verify running and completed alternate
        statuses = [s for _, s in callback_calls]
        for i in range(0, len(statuses), 2):
            assert statuses[i] == "running"
            assert statuses[i + 1] == "completed"
