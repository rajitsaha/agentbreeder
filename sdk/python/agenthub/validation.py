"""Validation utilities for AgentBreeder agent configurations.

Checks that the agent config is well-formed before serialization or
deployment. Returns a list of human-readable error strings (empty = valid).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent

# Slug pattern: lowercase alphanumeric + hyphens, 1-128 chars
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,127}$")

# Semver pattern (simplified but practical)
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(-[0-9A-Za-z\-]+(\.[0-9A-Za-z\-]+)*)?"
    r"(\+[0-9A-Za-z\-]+(\.[0-9A-Za-z\-]+)*)?$"
)

VALID_FRAMEWORKS = {
    "langgraph",
    "crewai",
    "claude_sdk",
    "openai_agents",
    "google_adk",
    "custom",
}


def validate_agent(agent: Agent) -> list[str]:
    """Validate an agent configuration.

    Returns:
        A list of error messages. An empty list means the config is valid.
    """
    errors: list[str] = []

    # Name is required and must be slug-friendly
    if not agent.config.name:
        errors.append("name is required")
    elif not _SLUG_RE.match(agent.config.name):
        errors.append(
            f"name '{agent.config.name}' is not slug-friendly "
            "(lowercase alphanumeric + hyphens, 1-128 chars)"
        )

    # Version must be valid semver
    if not agent.config.version:
        errors.append("version is required")
    elif not _SEMVER_RE.match(agent.config.version):
        errors.append(f"version '{agent.config.version}' is not valid semver (expected X.Y.Z)")

    # Team is required
    if not agent.config.team:
        errors.append("team is required")

    # Framework must be a known value
    if agent.config.framework not in VALID_FRAMEWORKS:
        errors.append(
            f"framework '{agent.config.framework}' is not valid "
            f"(must be one of: {', '.join(sorted(VALID_FRAMEWORKS))})"
        )

    # Model should be configured
    if agent.config.model is None:
        errors.append("model is required (use .with_model() to configure)")

    return errors
