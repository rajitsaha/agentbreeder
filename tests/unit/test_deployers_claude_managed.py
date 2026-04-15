"""Unit tests for the Claude Managed Agents deployer.

All Anthropic API calls are mocked — no real API key or beta access required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.config_parser import (
    AccessConfig,
    AgentConfig,
    ClaudeManagedConfig,
    CloudType,
    DeployConfig,
    FrameworkType,
    ModelConfig,
    PromptsConfig,
)
from engine.deployers.base import DeployResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config(
    *,
    name: str = "my-claude-agent",
    version: str = "1.0.0",
    system_prompt: str = "You are a helpful assistant.",
) -> AgentConfig:
    return AgentConfig(
        name=name,
        version=version,
        description="Test Claude Managed Agent",
        team="engineering",
        owner="alice@example.com",
        framework=FrameworkType.claude_sdk,
        model=ModelConfig(primary="claude-sonnet-4-6"),
        deploy=DeployConfig(cloud=CloudType.claude_managed),
        access=AccessConfig(),
        prompts=PromptsConfig(system=system_prompt),
        claude_managed=ClaudeManagedConfig(),
    )


def _make_deployer():
    from engine.deployers.claude_managed import ClaudeManagedDeployer

    return ClaudeManagedDeployer()


def _make_mock_client(agent_id: str = "agent_abc123", env_id: str = "env_xyz789"):
    mock_agent = MagicMock()
    mock_agent.id = agent_id
    mock_agent.version = 1

    mock_env = MagicMock()
    mock_env.id = env_id

    client = MagicMock()
    client.beta.agents.create = AsyncMock(return_value=mock_agent)
    client.beta.environments.create = AsyncMock(return_value=mock_env)
    client.beta.agents.delete = AsyncMock()
    client.beta.environments.delete = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# config_parser integration
# ---------------------------------------------------------------------------


class TestClaudeManagedConfigParser:
    def test_cloud_type_enum_has_claude_managed(self) -> None:
        assert CloudType.claude_managed == "claude-managed"

    def test_agent_config_accepts_claude_managed_cloud(self) -> None:
        config = _make_agent_config()
        assert config.deploy.cloud == CloudType.claude_managed

    def test_claude_managed_tools_default_to_full_toolset(self) -> None:
        cfg = ClaudeManagedConfig()
        assert len(cfg.tools) == 1
        assert cfg.tools[0].type == "agent_toolset_20260401"

    def test_claude_managed_networking_defaults_to_unrestricted(self) -> None:
        cfg = ClaudeManagedConfig()
        assert cfg.environment.networking == "unrestricted"

    def test_claude_managed_field_on_agent_config(self) -> None:
        config = _make_agent_config()
        assert config.claude_managed is not None
        assert config.claude_managed.environment.networking == "unrestricted"


# ---------------------------------------------------------------------------
# provision
# ---------------------------------------------------------------------------


class TestProvision:
    @pytest.mark.asyncio
    async def test_provision_calls_create_agent_and_environment(self) -> None:
        deployer = _make_deployer()
        config = _make_agent_config()
        mock_client = _make_mock_client()

        with patch(
            "engine.deployers.claude_managed._get_anthropic_client",
            return_value=mock_client,
        ):
            result = await deployer.provision(config)

        mock_client.beta.agents.create.assert_awaited_once()
        mock_client.beta.environments.create.assert_awaited_once()

        assert result.endpoint_url == "anthropic://agents/agent_abc123?env=env_xyz789"
        assert result.resource_ids["agent_id"] == "agent_abc123"
        assert result.resource_ids["environment_id"] == "env_xyz789"

    @pytest.mark.asyncio
    async def test_provision_maps_model_and_system_prompt(self) -> None:
        deployer = _make_deployer()
        config = _make_agent_config()
        mock_client = _make_mock_client()

        with patch(
            "engine.deployers.claude_managed._get_anthropic_client",
            return_value=mock_client,
        ):
            await deployer.provision(config)

        create_kwargs = mock_client.beta.agents.create.call_args.kwargs
        assert create_kwargs["model"] == "claude-sonnet-4-6"
        assert create_kwargs["system"] == "You are a helpful assistant."
        assert create_kwargs["name"] == "my-claude-agent"

    @pytest.mark.asyncio
    async def test_provision_maps_tools_from_claude_managed_config(self) -> None:
        deployer = _make_deployer()
        config = _make_agent_config()
        mock_client = _make_mock_client()

        with patch(
            "engine.deployers.claude_managed._get_anthropic_client",
            return_value=mock_client,
        ):
            await deployer.provision(config)

        create_kwargs = mock_client.beta.agents.create.call_args.kwargs
        assert len(create_kwargs["tools"]) == 1
        assert create_kwargs["tools"][0]["type"] == "agent_toolset_20260401"

    @pytest.mark.asyncio
    async def test_provision_stores_agent_and_env_ids(self) -> None:
        deployer = _make_deployer()
        config = _make_agent_config()
        mock_client = _make_mock_client("agent_111", "env_222")

        with patch(
            "engine.deployers.claude_managed._get_anthropic_client",
            return_value=mock_client,
        ):
            await deployer.provision(config)

        assert deployer._agent_id == "agent_111"
        assert deployer._environment_id == "env_222"

    @pytest.mark.asyncio
    async def test_provision_raises_import_error_without_anthropic_sdk(self) -> None:
        deployer = _make_deployer()
        config = _make_agent_config()

        with patch(
            "engine.deployers.claude_managed._get_anthropic_client",
            side_effect=ImportError("anthropic not installed"),
        ):
            with pytest.raises(ImportError, match="pip install anthropic"):
                await deployer.provision(config)

    @pytest.mark.asyncio
    async def test_provision_uses_default_system_prompt_when_none_set(self) -> None:
        deployer = _make_deployer()
        config = AgentConfig(
            name="my-agent",
            version="1.0.0",
            description="An agent",
            team="eng",
            owner="alice@example.com",
            framework=FrameworkType.claude_sdk,
            model=ModelConfig(primary="claude-sonnet-4-6"),
            deploy=DeployConfig(cloud=CloudType.claude_managed),
            access=AccessConfig(),
            claude_managed=ClaudeManagedConfig(),
        )
        mock_client = _make_mock_client()

        with patch(
            "engine.deployers.claude_managed._get_anthropic_client",
            return_value=mock_client,
        ):
            await deployer.provision(config)

        create_kwargs = mock_client.beta.agents.create.call_args.kwargs
        assert "my-agent" in create_kwargs["system"]

    @pytest.mark.asyncio
    async def test_provision_uses_networking_from_claude_managed_config(self) -> None:
        from engine.config_parser import ClaudeManagedEnvironmentConfig

        deployer = _make_deployer()
        config = _make_agent_config()
        config.claude_managed = ClaudeManagedConfig(
            environment=ClaudeManagedEnvironmentConfig(networking="restricted")
        )
        mock_client = _make_mock_client()

        with patch(
            "engine.deployers.claude_managed._get_anthropic_client",
            return_value=mock_client,
        ):
            await deployer.provision(config)

        env_kwargs = mock_client.beta.environments.create.call_args.kwargs
        assert env_kwargs["config"]["networking"]["type"] == "restricted"


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------


class TestDeploy:
    @pytest.mark.asyncio
    async def test_deploy_returns_anthropic_endpoint(self) -> None:
        deployer = _make_deployer()
        deployer._agent_id = "agent_abc123"
        deployer._environment_id = "env_xyz789"

        config = _make_agent_config()
        image = MagicMock()  # ignored for claude-managed
        result = await deployer.deploy(config, image)

        assert result.endpoint_url == "anthropic://agents/agent_abc123?env=env_xyz789"
        assert result.status == "running"
        assert result.agent_name == "my-claude-agent"
        assert result.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_deploy_raises_if_provision_not_called(self) -> None:
        deployer = _make_deployer()
        config = _make_agent_config()
        image = MagicMock()

        with pytest.raises(RuntimeError, match="provision"):
            await deployer.deploy(config, image)

    @pytest.mark.asyncio
    async def test_deploy_container_id_is_agent_id(self) -> None:
        deployer = _make_deployer()
        deployer._agent_id = "agent_abc123"
        deployer._environment_id = "env_xyz789"

        config = _make_agent_config()
        result = await deployer.deploy(config, MagicMock())

        assert result.container_id == "agent_abc123"


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_always_returns_healthy(self) -> None:
        deployer = _make_deployer()
        result = DeployResult(
            endpoint_url="anthropic://agents/agent_abc123?env=env_xyz789",
            container_id="agent_abc123",
            status="running",
            agent_name="my-claude-agent",
            version="1.0.0",
        )
        health = await deployer.health_check(result)
        assert health.healthy is True
        assert health.checks["managed_by_anthropic"] is True


# ---------------------------------------------------------------------------
# teardown
# ---------------------------------------------------------------------------


class TestTeardown:
    @pytest.mark.asyncio
    async def test_teardown_deletes_agent_and_environment(self) -> None:
        deployer = _make_deployer()
        deployer._agent_id = "agent_abc123"
        deployer._environment_id = "env_xyz789"

        mock_client = MagicMock()
        mock_client.beta.agents.delete = AsyncMock()
        mock_client.beta.environments.delete = AsyncMock()

        with patch(
            "engine.deployers.claude_managed._get_anthropic_client",
            return_value=mock_client,
        ):
            await deployer.teardown("my-claude-agent")

        mock_client.beta.agents.delete.assert_awaited_once_with("agent_abc123")
        mock_client.beta.environments.delete.assert_awaited_once_with("env_xyz789")

    @pytest.mark.asyncio
    async def test_teardown_skips_when_ids_not_set(self) -> None:
        deployer = _make_deployer()
        mock_client = MagicMock()
        mock_client.beta.agents.delete = AsyncMock()
        mock_client.beta.environments.delete = AsyncMock()

        with patch(
            "engine.deployers.claude_managed._get_anthropic_client",
            return_value=mock_client,
        ):
            await deployer.teardown("ghost-agent")

        mock_client.beta.agents.delete.assert_not_awaited()
        mock_client.beta.environments.delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# get_logs
# ---------------------------------------------------------------------------


class TestGetLogs:
    @pytest.mark.asyncio
    async def test_get_logs_returns_session_guidance(self) -> None:
        deployer = _make_deployer()
        deployer._agent_id = "agent_abc123"
        logs = await deployer.get_logs("my-claude-agent")
        assert len(logs) == 1
        log = logs[0].lower()
        assert "session" in log or "anthropic" in log

    @pytest.mark.asyncio
    async def test_get_logs_includes_agent_id(self) -> None:
        deployer = _make_deployer()
        deployer._agent_id = "agent_abc123"
        logs = await deployer.get_logs("my-claude-agent")
        assert "agent_abc123" in logs[0]


# ---------------------------------------------------------------------------
# _resolve_system_prompt
# ---------------------------------------------------------------------------


class TestResolveSystemPrompt:
    def test_returns_inline_system_prompt(self) -> None:
        deployer = _make_deployer()
        config = _make_agent_config(system_prompt="Custom prompt.")
        prompt = deployer._resolve_system_prompt(config)
        assert prompt == "Custom prompt."

    def test_returns_default_when_no_prompt_set(self) -> None:
        deployer = _make_deployer()
        config = AgentConfig(
            name="my-agent",
            version="1.0.0",
            description="An agent",
            team="eng",
            owner="alice@example.com",
            framework=FrameworkType.claude_sdk,
            model=ModelConfig(primary="claude-sonnet-4-6"),
            deploy=DeployConfig(cloud=CloudType.claude_managed),
            access=AccessConfig(),
            claude_managed=ClaudeManagedConfig(),
        )
        prompt = deployer._resolve_system_prompt(config)
        assert "my-agent" in prompt


# ---------------------------------------------------------------------------
# Deployer registry
# ---------------------------------------------------------------------------


class TestDeployerRegistry:
    def test_claude_managed_cloud_routes_to_claude_managed_deployer(self) -> None:
        from engine.deployers import get_deployer
        from engine.deployers.claude_managed import ClaudeManagedDeployer

        deployer = get_deployer(CloudType.claude_managed)
        assert isinstance(deployer, ClaudeManagedDeployer)
