"""RBAC and governance checks.

For v0.1 this is a stub that always passes.
Full RBAC engine is planned for v0.3.
"""

from __future__ import annotations

import logging

from engine.config_parser import AgentConfig

logger = logging.getLogger(__name__)


class RBACDeniedError(Exception):
    """Raised when a user is not authorized to perform an action."""

    def __init__(self, user: str, team: str, action: str) -> None:
        self.user = user
        self.team = team
        self.action = action
        super().__init__(f"User '{user}' is not authorized to {action} for team '{team}'")


def check_rbac(config: AgentConfig, user: str) -> None:
    """Check if the user is authorized to deploy this agent.

    For v0.1 this always passes. Full RBAC in v0.3.
    """
    logger.debug("RBAC check: user=%s, team=%s (stub — always passes)", user, config.team)
