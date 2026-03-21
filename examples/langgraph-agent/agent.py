"""A simple hello-world LangGraph agent.

This is the minimal example — a single-node graph that echoes messages.
No LLM API key needed for this demo.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import StateGraph


class AgentState(TypedDict):
    message: str
    response: str


def respond(state: AgentState) -> AgentState:
    """Process the message and generate a response."""
    message = state.get("message", "")
    return {
        "message": message,
        "response": f"Hello from AgentBreeder! You said: {message}",
    }


# Build the graph
builder = StateGraph(AgentState)
builder.add_node("respond", respond)
builder.set_entry_point("respond")
builder.set_finish_point("respond")

# Export as 'graph' — the AgentBreeder server wrapper looks for this
graph = builder.compile()
