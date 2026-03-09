"""Dependency resolver.

Resolves registry references (ref: tools/zendesk-mcp) into concrete artifacts.
For v0.1 this is a stub — references are passed through unchanged.
"""

from __future__ import annotations

import logging

from engine.config_parser import AgentConfig

logger = logging.getLogger(__name__)


class ResolutionError(Exception):
    """Raised when a registry reference cannot be resolved."""


def resolve_dependencies(config: AgentConfig) -> AgentConfig:
    """Resolve all registry references in the config.

    For v0.1 this is a no-op — returns config unchanged.
    Full resolution from the registry is planned for v0.2.
    """
    refs = []
    for tool in config.tools:
        if tool.ref:
            refs.append(tool.ref)
    for kb in config.knowledge_bases:
        refs.append(kb.ref)

    if refs:
        logger.debug("Dependency resolution stub — passing through refs: %s", refs)

    return config
