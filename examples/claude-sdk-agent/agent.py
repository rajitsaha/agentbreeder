"""Claude SDK agent with tool use example.

Exposes an AsyncAnthropic client as `agent` so the AgentBreeder server
wrapper can discover and invoke it. The server wrapper handles the
messages.create() call; the tool-use loop below is an example of how
you might handle multi-turn tool use in your own agent callable instead.

To use the full tool-use loop, replace `agent = AsyncAnthropic()` with
`agent = weather_agent` (the async callable defined below).
"""

from __future__ import annotations

import json
import os

import anthropic

# ── Simple export: let the server wrapper drive the conversation ──────────────
# The AgentBreeder server wrapper will call:
#   client.messages.create(model=..., max_tokens=1024, messages=[...])
# AGENT_MODEL and AGENT_SYSTEM_PROMPT are read from env vars at runtime.
agent = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ── Tool definition ───────────────────────────────────────────────────────────
TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a given city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city name, e.g. 'London'.",
                }
            },
            "required": ["city"],
        },
    }
]


def _get_weather(city: str) -> str:
    """Dummy weather implementation — replace with a real API call."""
    return json.dumps({"city": city, "temperature_c": 22, "condition": "partly cloudy"})


# ── Full tool-use loop (alternative export) ───────────────────────────────────
async def weather_agent(prompt: str) -> str:
    """Run a multi-turn Claude conversation with tool use.

    Swap `agent = AsyncAnthropic()` for `agent = weather_agent` in this
    file if you want AgentBreeder to call this function instead.
    """
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    system = os.getenv(
        "AGENT_SYSTEM_PROMPT",
        "You are a helpful weather assistant. Use the get_weather tool to answer questions.",
    )
    model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    messages: list[anthropic.types.MessageParam] = [{"role": "user", "content": prompt}]

    while True:
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            # Return the first text block
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        if response.stop_reason == "tool_use":
            # Process tool calls
            tool_results: list[anthropic.types.ToolResultBlockParam] = []
            for block in response.content:
                if block.type == "tool_use":
                    if block.name == "get_weather":
                        result = _get_weather(**block.input)  # type: ignore[arg-type]
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )

            # Add assistant turn + tool results to the conversation
            messages.append({"role": "assistant", "content": response.content})  # type: ignore[arg-type]
            messages.append({"role": "user", "content": tool_results})  # type: ignore[arg-type]
            continue

        # Unexpected stop reason — return whatever text we have
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""
