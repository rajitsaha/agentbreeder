"""Advanced Agent Garden SDK example.

Demonstrates middleware, event hooks, custom routing, dynamic tool selection,
and agent state management.

Usage:
    python agent.py
"""

from __future__ import annotations

import logging
from typing import Any

from agenthub import Agent, Tool

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------
# Define tools from Python functions
# ---------------------------------------------------------------


def search_knowledge_base(query: str, max_results: int = 5) -> str:
    """Search the internal knowledge base for relevant articles."""
    return f"Found {max_results} results for: {query}"


def escalate_to_human(reason: str, priority: int = 1) -> str:
    """Escalate the conversation to a human agent."""
    return f"Escalated (priority={priority}): {reason}"


search_tool = Tool.from_function(search_knowledge_base)
escalate_tool = Tool.from_function(escalate_to_human)

# ---------------------------------------------------------------
# Build the agent
# ---------------------------------------------------------------

agent = (
    Agent(
        "smart-support",
        version="2.0.0",
        team="support",
        owner="alice@company.com",
        description="Advanced support agent with custom routing and middleware",
    )
    .with_model(primary="claude-sonnet-4", fallback="gpt-4o", temperature=0.3)
    .with_prompt(system="You are an expert support agent. Be concise and helpful.")
    .with_tool(search_tool)
    .with_tool(escalate_tool)
    .with_tool(Tool.from_ref("tools/zendesk-mcp"))
    .with_memory(backend="postgresql", max_messages=200)
    .with_guardrail("pii_detection")
    .with_guardrail("hallucination_check")
    .with_guardrail("content_filter")
    .with_deploy(
        cloud="aws",
        runtime="ecs-fargate",
        region="us-east-1",
        scaling={"min": 2, "max": 20, "target_cpu": 60},
    )
    .tag("support", "production", "v2")
)

# ---------------------------------------------------------------
# Middleware — runs on every turn
# ---------------------------------------------------------------


def logging_middleware(message: str, context: dict[str, Any]) -> dict[str, Any]:
    """Log every incoming message."""
    turn_count = agent.state.get("turn_count", 0) + 1
    agent.state["turn_count"] = turn_count
    logging.info("Turn %d: %s", turn_count, message[:100])
    return context


def rate_limit_middleware(message: str, context: dict[str, Any]) -> dict[str, Any]:
    """Track message rate per session."""
    session_id = context.get("session_id", "unknown")
    rates = agent.state.setdefault("rates", {})
    rates[session_id] = rates.get(session_id, 0) + 1
    return context


agent.use(logging_middleware)
agent.use(rate_limit_middleware)

# ---------------------------------------------------------------
# Event hooks
# ---------------------------------------------------------------


def on_tool_call(tool_name: str, args: dict[str, Any]) -> None:
    """Called before every tool invocation."""
    logging.info("Calling tool '%s' with args: %s", tool_name, args)


def on_error(error: Exception) -> None:
    """Called when the agent encounters an error."""
    logging.error("Agent error: %s", error)
    agent.state.setdefault("errors", []).append(str(error))


agent.on("tool_call", on_tool_call)
agent.on("error", on_error)


# ---------------------------------------------------------------
# Custom routing — subclass pattern
# ---------------------------------------------------------------


class SmartSupportAgent(Agent):
    """Agent with custom routing logic."""

    def route(self, message: str, context: dict[str, Any]) -> str | None:
        """Route to escalation for angry customers."""
        anger_keywords = {"furious", "lawsuit", "terrible", "worst"}
        if any(word in message.lower() for word in anger_keywords):
            return "escalate_to_human"
        return None

    def select_tools(self, message: str) -> list[Tool]:
        """Only expose search for question-type messages."""
        if "?" in message:
            return [t for t in self._tools if t.name == "search_knowledge_base"]
        return list(self._tools)


if __name__ == "__main__":
    # Validate
    errors = agent.validate()
    if errors:
        print("Validation errors:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("Agent is valid!")

    # Show generated YAML
    print("\n--- agent.yaml ---")
    print(agent.to_yaml())

    # Show tool schemas
    print("--- Tool schemas ---")
    for tool in agent._tools:
        print(f"{tool.name}: {tool.input_schema}")

    # Demonstrate state
    agent.state["initialized"] = True
    print(f"\nAgent state: {agent.state}")
