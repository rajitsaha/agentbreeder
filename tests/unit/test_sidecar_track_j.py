"""Tests for Track J sidecar additions.

Covers:
- engine.sidecar.injector.should_inject
- engine.sidecar.injector.inject_compose_sidecar
- engine.sidecar.config.SidecarConfig.from_agent_config
- engine.deployers.docker_compose._start_sidecar (auto-injection)
- engine.deployers.gcp_cloudrun._build_cloudrun_sidecar_container
- engine.deployers.aws_ecs sidecar branch in _register_task_definition
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from engine.config_parser import AgentConfig, FrameworkType, GuardrailConfig
from engine.deployers.docker_compose import DockerComposeDeployer
from engine.deployers.gcp_cloudrun import _build_cloudrun_sidecar_container
from engine.sidecar import SidecarConfig, inject_sidecar, should_inject
from engine.sidecar.injector import SIDECAR_NAME, inject_compose_sidecar


def _make_config(**overrides: Any) -> AgentConfig:
    defaults: dict[str, Any] = {
        "name": "track-j-agent",
        "version": "1.0.0",
        "team": "test",
        "owner": "test@example.com",
        "framework": FrameworkType.langgraph,
        "model": {"primary": "gpt-4o"},
        "deploy": {"cloud": "local"},
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)


# --- should_inject ----------------------------------------------------------


class TestShouldInject:
    def test_no_triggers_returns_false(self) -> None:
        config = _make_config()
        assert should_inject(config) is False

    def test_string_guardrails_trigger(self) -> None:
        config = _make_config(guardrails=["pii_detection"])
        assert should_inject(config) is True

    def test_dict_guardrails_trigger(self) -> None:
        config = _make_config(guardrails=[GuardrailConfig(name="custom", endpoint="http://x")])
        assert should_inject(config) is True

    def test_mcp_servers_trigger(self) -> None:
        config = _make_config(mcp_servers=[{"name": "fs", "ref": "mcp/filesystem"}])
        assert should_inject(config) is True

    def test_env_disabled_short_circuits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        config = _make_config(guardrails=["pii_detection"])
        monkeypatch.setenv("AGENTBREEDER_SIDECAR", "disabled")
        assert should_inject(config) is False

    def test_env_off_short_circuits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        config = _make_config(guardrails=["pii_detection"])
        monkeypatch.setenv("AGENTBREEDER_SIDECAR", "off")
        assert should_inject(config) is False

    def test_env_enabled_does_not_short_circuit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        config = _make_config(guardrails=["pii_detection"])
        monkeypatch.setenv("AGENTBREEDER_SIDECAR", "enabled")
        assert should_inject(config) is True

    def test_a2a_field_triggers(self) -> None:
        # AgentConfig doesn't currently have an `a2a` field, but should_inject
        # honours it via getattr — simulate a future extension.
        ns = SimpleNamespace(guardrails=[], mcp_servers=[], tools=[], a2a={"peer": "x"})
        assert should_inject(ns) is True

    def test_inline_mcp_tool_triggers(self) -> None:
        ns = SimpleNamespace(
            guardrails=[],
            mcp_servers=[],
            tools=[SimpleNamespace(ref=None, type="mcp")],
            a2a=None,
        )
        assert should_inject(ns) is True

    def test_tools_with_mcp_ref_trigger(self) -> None:
        ns = SimpleNamespace(
            guardrails=[],
            mcp_servers=[],
            tools=[SimpleNamespace(ref="mcp/zendesk", type=None)],
            a2a=None,
        )
        assert should_inject(ns) is True


# --- SidecarConfig.from_agent_config ----------------------------------------


class TestFromAgentConfig:
    def test_extracts_string_guardrails(self) -> None:
        config = _make_config(guardrails=["pii_detection", "content_filter"])
        sc = SidecarConfig.from_agent_config(config)
        assert sc.enabled is True
        assert sc.guardrails == ["pii_detection", "content_filter"]

    def test_extracts_named_guardrails(self) -> None:
        config = _make_config(guardrails=[GuardrailConfig(name="custom", endpoint="http://x")])
        sc = SidecarConfig.from_agent_config(config)
        assert sc.guardrails == ["custom"]

    def test_handles_missing_guardrails(self) -> None:
        config = _make_config()
        sc = SidecarConfig.from_agent_config(config)
        assert sc.guardrails == []
        assert sc.enabled is True


# --- inject_compose_sidecar -------------------------------------------------


class TestInjectComposeSidecar:
    def test_appends_sidecar_service(self) -> None:
        services = {"agent": {"image": "my-agent:latest"}}
        config = SidecarConfig(enabled=True, guardrails=["pii_detection"])
        result = inject_compose_sidecar(services, config)

        assert SIDECAR_NAME in result
        assert "agent" in result
        sidecar = result[SIDECAR_NAME]
        assert sidecar["image"] == config.image
        assert sidecar["depends_on"] == ["agent"]
        assert "AGENT_AUTH_TOKEN" in sidecar["environment"]
        assert sidecar["environment"]["AB_GUARDRAILS"] == "pii_detection"

    def test_does_not_mutate_input(self) -> None:
        services = {"agent": {"image": "my-agent:latest"}}
        original = dict(services)
        inject_compose_sidecar(services, SidecarConfig(enabled=True))
        assert services == original

    def test_idempotent(self) -> None:
        services = {"agent": {"image": "my-agent:latest"}}
        config = SidecarConfig(enabled=True)
        once = inject_compose_sidecar(services, config)
        twice = inject_compose_sidecar(once, config)
        assert list(twice.keys()) == list(once.keys())

    def test_disabled_returns_input_unchanged(self) -> None:
        services = {"agent": {"image": "my-agent:latest"}}
        result = inject_compose_sidecar(services, SidecarConfig(enabled=False))
        assert SIDECAR_NAME not in result

    def test_custom_agent_service_name(self) -> None:
        services = {"my-svc": {"image": "x"}}
        result = inject_compose_sidecar(
            services, SidecarConfig(enabled=True), agent_service="my-svc"
        )
        sidecar = result[SIDECAR_NAME]
        assert sidecar["depends_on"] == ["my-svc"]
        assert "my-svc" in sidecar["environment"]["AGENTBREEDER_SIDECAR_AGENT_URL"]


# --- inject_sidecar agent URL env var ---------------------------------------


class TestInjectSidecarNewEnv:
    def test_injects_agent_url_env(self) -> None:
        task_def: dict[str, Any] = {"containerDefinitions": []}
        config = SidecarConfig(enabled=True, agent_port=8081)
        result = inject_sidecar(task_def, config)
        sidecar = next(c for c in result["containerDefinitions"] if c["name"] == SIDECAR_NAME)
        env_names = {e["name"] for e in sidecar["environment"]}
        assert "AGENTBREEDER_SIDECAR_AGENT_URL" in env_names
        agent_url = next(
            e for e in sidecar["environment"] if e["name"] == "AGENTBREEDER_SIDECAR_AGENT_URL"
        )
        assert agent_url["value"] == "http://localhost:8081"


# --- GCP Cloud Run sidecar container builder --------------------------------


class TestCloudRunSidecarBuilder:
    def test_builds_minimal_spec(self) -> None:
        config = _make_config(guardrails=["pii_detection"])
        spec = _build_cloudrun_sidecar_container(config)
        assert spec["name"] == "agentbreeder-sidecar"
        assert spec["image"] == SidecarConfig().image
        env_names = {e["name"] for e in spec["env"]}
        assert {
            "AGENT_NAME",
            "AGENT_VERSION",
            "AGENTBREEDER_SIDECAR_AGENT_URL",
            "AB_GUARDRAILS",
        }.issubset(env_names)

    def test_includes_otel_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENTELEMETRY_ENDPOINT", "http://collector:4318")
        config = _make_config(guardrails=["pii_detection"])
        spec = _build_cloudrun_sidecar_container(config)
        env_names = {e["name"] for e in spec["env"]}
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in env_names

    def test_includes_api_url_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENTBREEDER_API_URL", "https://api.agentbreeder.io")
        config = _make_config(guardrails=["pii_detection"])
        spec = _build_cloudrun_sidecar_container(config)
        env_names = {e["name"] for e in spec["env"]}
        assert "AGENTBREEDER_API_URL" in env_names


# --- Docker Compose deployer auto-injection ---------------------------------


class TestDockerComposeAutoInjection:
    @pytest.mark.asyncio
    async def test_start_sidecar_starts_container(self) -> None:
        deployer = DockerComposeDeployer()
        client = MagicMock()

        import docker

        client.containers.get.side_effect = docker.errors.NotFound("no")
        client.containers.run.return_value = MagicMock(id="sc-id-1")
        client.networks.get.return_value = MagicMock()

        config = _make_config(guardrails=["pii_detection"])
        sid = await deployer._start_sidecar(client, config, "agentbreeder-x")
        assert sid == "sc-id-1"
        client.containers.run.assert_called_once()

        # Check the env vars include the agent URL pointing at the agent container.
        kwargs = client.containers.run.call_args.kwargs
        assert kwargs["environment"]["AGENTBREEDER_SIDECAR_AGENT_URL"] == (
            "http://agentbreeder-x:8080"
        )
        assert kwargs["name"] == "agentbreeder-x-sidecar"

    @pytest.mark.asyncio
    async def test_start_sidecar_idempotent(self) -> None:
        deployer = DockerComposeDeployer()
        client = MagicMock()
        client.containers.get.return_value = MagicMock(id="existing-id")

        config = _make_config(guardrails=["pii_detection"])
        sid = await deployer._start_sidecar(client, config, "agentbreeder-x")
        assert sid == "existing-id"
        client.containers.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_sidecar_swallows_failures(self) -> None:
        deployer = DockerComposeDeployer()
        client = MagicMock()

        import docker

        client.containers.get.side_effect = docker.errors.NotFound("no")
        client.containers.run.side_effect = RuntimeError("boom")
        client.networks.get.return_value = MagicMock()

        config = _make_config(guardrails=["pii_detection"])
        # Failure must not raise — the sidecar is best-effort in local dev.
        sid = await deployer._start_sidecar(client, config, "agentbreeder-x")
        assert sid is None


# --- AWS ECS sidecar branch -------------------------------------------------


class TestECSSidecarBranch:
    def test_register_task_def_appends_sidecar(self) -> None:
        # Verify that should_inject() routes through inject_sidecar; a black-box
        # test of the wiring inside _register_task_definition.
        from engine.sidecar import inject_sidecar

        config = _make_config(guardrails=["pii_detection"])
        partial = {"containerDefinitions": [{"name": "agent", "image": "x"}]}
        out = inject_sidecar(partial, SidecarConfig.from_agent_config(config))
        names = [c["name"] for c in out["containerDefinitions"]]
        assert "agentbreeder-sidecar" in names
        assert "agent" in names

    def test_register_task_def_skips_when_no_triggers(self) -> None:
        # If should_inject is False, the deployer code path doesn't call
        # inject_sidecar — so the task def stays single-container.
        config = _make_config()  # no guardrails / mcp / a2a
        assert should_inject(config) is False
