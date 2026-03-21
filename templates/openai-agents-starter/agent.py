"""OpenAI Agents SDK starter agent with function tools.

Demonstrates:
- Agent creation with system instructions
- @function_tool decorator for tool definitions
- Guardrail integration
- AgentBreeder export pattern

Export the agent as `agent` — AgentBreeder's server wrapper looks for this.
"""

from __future__ import annotations

from agents import Agent, Runner, function_tool


@function_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: Name of the city to get weather for.

    Returns:
        Weather information as a formatted string.
    """
    # Placeholder — integrate with a real weather API in production
    return (
        f"Weather in {city}:\n"
        f"Temperature: 72F (22C)\n"
        f"Conditions: Partly cloudy\n"
        f"Humidity: 45%\n"
        f"Wind: 8 mph NW"
    )


@function_tool
def search_knowledge(query: str) -> str:
    """Search the knowledge base for information.

    Args:
        query: The search query.

    Returns:
        Relevant knowledge base entries.
    """
    # Placeholder — integrate with your RAG pipeline in production
    return (
        f"Knowledge base results for '{query}':\n"
        f"1. [Doc A] Relevant information about {query}\n"
        f"2. [Doc B] Additional context for {query}"
    )


# Build the agent — exported as 'agent' for the AgentBreeder server wrapper
agent = Agent(
    name="OpenAI Agents Starter",
    instructions=(
        "You are a helpful assistant. Use your tools to provide accurate information. "
        "When asked about weather, use the get_weather tool. For general questions, "
        "search the knowledge base first. Be concise and helpful."
    ),
    tools=[get_weather, search_knowledge],
)


async def main() -> None:
    """Run the agent interactively for local testing."""
    result = await Runner.run(agent, "What's the weather in San Francisco?")
    print(f"Agent response: {result.final_output}")  # noqa: T201


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
