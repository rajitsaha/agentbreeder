"""Google ADK example agent for AgentBreeder.

Defines a simple assistant with a clock tool using the Google Agent Development Kit.
The `root_agent` export is picked up by the AgentBreeder server wrapper at runtime.
"""

from __future__ import annotations

from datetime import UTC, datetime

from google.adk.agents import Agent


def get_current_time() -> dict:
    """Return the current UTC time as an ISO 8601 string."""
    return {"utc_time": datetime.now(UTC).isoformat()}


root_agent = Agent(
    name="gemini-assistant",
    model="gemini-2.0-flash",
    description="A helpful assistant that can answer questions and check the current time.",
    instruction=(
        "You are a helpful assistant. Answer user questions clearly and concisely. "
        "When the user asks about the current time, use the get_current_time tool."
    ),
    tools=[get_current_time],
)
