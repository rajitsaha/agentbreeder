"""Runtime builder registry.

Maps framework types to their runtime builder implementations.
"""

from __future__ import annotations

from engine.config_parser import FrameworkType
from engine.runtimes.base import RuntimeBuilder
from engine.runtimes.claude_sdk import ClaudeSDKRuntime
from engine.runtimes.crewai import CrewAIRuntime
from engine.runtimes.custom import CustomRuntime
from engine.runtimes.google_adk import GoogleADKRuntime
from engine.runtimes.langgraph import LangGraphRuntime
from engine.runtimes.openai_agents import OpenAIAgentsRuntime

RUNTIMES: dict[FrameworkType, type[RuntimeBuilder]] = {
    FrameworkType.langgraph: LangGraphRuntime,
    FrameworkType.openai_agents: OpenAIAgentsRuntime,
    FrameworkType.crewai: CrewAIRuntime,
    FrameworkType.claude_sdk: ClaudeSDKRuntime,
    FrameworkType.google_adk: GoogleADKRuntime,
    FrameworkType.custom: CustomRuntime,
}


def get_runtime(framework: FrameworkType) -> RuntimeBuilder:
    """Get the runtime builder for a given framework.

    Raises KeyError if the framework is not yet supported.
    """
    builder_cls = RUNTIMES.get(framework)
    if builder_cls is None:
        supported = ", ".join(r.value for r in RUNTIMES)
        msg = (
            f"Framework '{framework.value}' is not yet supported. "
            f"Supported frameworks: {supported}. "
            f"See CONTRIBUTING.md for how to add a new runtime."
        )
        raise KeyError(msg)
    return builder_cls()
