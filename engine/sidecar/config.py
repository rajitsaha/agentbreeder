"""Sidecar configuration dataclass.

Track J: cross-cutting concerns layer (tracing, cost, guardrails, A2A, MCP).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

# Single source of truth for the sidecar image — kept as a constant so deployers
# never accidentally diverge.
DEFAULT_SIDECAR_IMAGE = "rajits/agentbreeder-sidecar:latest"


@dataclass
class SidecarConfig:
    """Runtime configuration for the AgentBreeder sidecar container.

    Populated either from the deploy.sidecar dict in agent.yaml, or
    auto-derived from the top-level agent config when guardrails / A2A / MCP
    are declared.
    """

    enabled: bool = True
    image: str = DEFAULT_SIDECAR_IMAGE
    otel_endpoint: str = field(default_factory=lambda: os.getenv("OPENTELEMETRY_ENDPOINT", ""))
    guardrails: list[str] = field(default_factory=list)
    cost_tracking: bool = True
    health_port: int = 8080
    # When sidecar is injected the agent listens on this internal port and
    # the sidecar forwards public traffic from health_port.
    agent_port: int = 8081
    auth_token_env: str = "AGENT_AUTH_TOKEN"
    api_url_env: str = "AGENTBREEDER_API_URL"

    @classmethod
    def from_deploy_config(cls, deploy_sidecar: dict[str, Any] | None) -> SidecarConfig:
        """Build a SidecarConfig from the deploy.sidecar dict in agent.yaml.

        Returns a default (enabled) config if deploy_sidecar is None.
        """
        if deploy_sidecar is None:
            return cls()
        return cls(
            enabled=deploy_sidecar.get("enabled", True),
            image=deploy_sidecar.get("image", DEFAULT_SIDECAR_IMAGE),
            guardrails=deploy_sidecar.get("guardrails", []),
            otel_endpoint=deploy_sidecar.get(
                "otel_endpoint",
                os.getenv("OPENTELEMETRY_ENDPOINT", ""),
            ),
            cost_tracking=deploy_sidecar.get("cost_tracking", True),
            agent_port=int(deploy_sidecar.get("agent_port", 8081)),
        )

    @classmethod
    def from_agent_config(cls, agent_config: Any) -> SidecarConfig:
        """Build a SidecarConfig from a parsed AgentConfig.

        Reads guardrails declared at the top level of agent.yaml and any
        deploy.env_vars hint. Used by deployers that auto-inject the sidecar.
        """
        guardrails = _normalise_guardrails(getattr(agent_config, "guardrails", []) or [])
        return cls(
            enabled=True,
            guardrails=guardrails,
        )


def _normalise_guardrails(raw: list[Any]) -> list[str]:
    """Reduce mixed (str | GuardrailConfig) lists down to a list of names."""
    out: list[str] = []
    for entry in raw:
        if isinstance(entry, str):
            out.append(entry)
        else:
            name = getattr(entry, "name", None)
            if name:
                out.append(str(name))
    return out
