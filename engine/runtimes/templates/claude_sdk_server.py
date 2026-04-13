"""AgentBreeder server wrapper for Claude SDK agents.

This file is copied into the agent container at build time.
It wraps any Claude SDK agent as a FastAPI server with /invoke and /health endpoints.

The agent.py in the container must export one of:
- agent: an anthropic.AsyncAnthropic or anthropic.Anthropic client, or
         an async callable `async def agent(input: str) -> str`, or
         an object with `async def run(input: str) -> str`
- app:   same types as above
- client: same types as above
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
from typing import Any

import json

from engine.tool_bridge import to_claude_tools
from engine.config_parser import ToolRef

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentbreeder.agent")

app = FastAPI(
    title="AgentBreeder Agent",
    description="Deployed by AgentBreeder",
    version=os.getenv("AGENT_VERSION", "0.1.0"),
)


class InvokeRequest(BaseModel):
    input: str
    config: dict[str, Any] | None = None


class InvokeResponse(BaseModel):
    output: Any
    metadata: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    agent_name: str
    version: str


def _load_agent() -> Any:
    """Dynamically load the agent from agent.py."""
    sys.path.insert(0, "/app")
    try:
        module = importlib.import_module("agent")
    except ImportError as e:
        logger.error("Failed to import agent module: %s", e)
        raise

    # Look for common Claude SDK exports
    for attr_name in ("agent", "app", "client"):
        if hasattr(module, attr_name):
            return getattr(module, attr_name)

    msg = (
        "agent.py must export one of: 'agent', 'app', or 'client'. "
        "This should be an anthropic.AsyncAnthropic client, an anthropic.Anthropic client, "
        "an async callable, or an object with an async run() method."
    )
    raise AttributeError(msg)


# Load agent at startup
_agent = None
_tools: list[dict] = []


@app.on_event("startup")
async def startup() -> None:
    global _agent, _tools  # noqa: PLW0603
    logger.info("Loading agent...")
    try:
        _agent = _load_agent()
        logger.info("Agent loaded successfully")
    except Exception:
        logger.warning("Agent module not loaded yet -- will retry on first request")
    # --- Tool bridge ---
    tools_json = os.getenv("AGENT_TOOLS_JSON", "[]")
    try:
        raw_tools = json.loads(tools_json)
        tool_refs = [ToolRef(**t) for t in raw_tools]
        _tools = to_claude_tools(tool_refs)
        if _tools:
            logger.info("Loaded %d Claude tool(s) from AGENT_TOOLS_JSON", len(_tools))
    except Exception:
        logger.exception(
            "Failed to load tools from AGENT_TOOLS_JSON -- proceeding with no tools"
        )
        _tools = []


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy" if _agent is not None else "loading",
        agent_name=os.getenv("AGENT_NAME", "unknown"),
        version=os.getenv("AGENT_VERSION", "0.1.0"),
    )


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest) -> InvokeResponse:
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not loaded yet")

    try:
        result = await _run_agent(request.input)
        return InvokeResponse(output=result)
    except Exception as e:
        logger.exception("Agent invocation failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/stream")
async def stream(request: InvokeRequest) -> StreamingResponse:
    """Stream Claude SDK responses as Server-Sent Events."""
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not loaded yet")
    return StreamingResponse(
        _stream_agent(request.input),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_agent(input_data: str) -> Any:
    """Async generator that yields SSE-formatted strings for Claude SDK agents."""
    import anthropic

    model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    system_prompt = os.getenv("AGENT_SYSTEM_PROMPT", "")
    max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "1024"))
    messages = [{"role": "user", "content": input_data}]

    if isinstance(_agent, anthropic.AsyncAnthropic):
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if _tools:
            kwargs["tools"] = _tools
        try:
            async with _agent.messages.stream(**kwargs) as stream:
                async for event in stream:
                    event_type_val = getattr(event, "type", "unknown")
                    payload: dict[str, Any] = {"type": event_type_val}
                    if (
                        event_type_val == "content_block_delta"
                        and hasattr(event, "delta")
                        and isinstance(getattr(event.delta, "text", None), str)
                    ):
                        payload["text"] = event.delta.text
                    yield f"data: {json.dumps(payload)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
    else:
        try:
            result = await _run_agent(input_data)
            yield f"data: {json.dumps({'type': 'result', 'text': result})}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    yield "data: [DONE]\n\n"


async def _run_agent(input_data: str) -> str:
    """Run the agent, dispatching based on the type of object loaded from agent.py."""
    import anthropic

    model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "1024"))
    system_prompt = os.getenv("AGENT_SYSTEM_PROMPT", "")
    messages = [{"role": "user", "content": input_data}]

    # anthropic.AsyncAnthropic client
    if isinstance(_agent, anthropic.AsyncAnthropic):
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if _tools:
            kwargs["tools"] = _tools
        response = await _agent.messages.create(**kwargs)
        return _extract_text(response)

    # anthropic.Anthropic (sync) client — run in thread to avoid blocking
    if isinstance(_agent, anthropic.Anthropic):
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if _tools:
            kwargs["tools"] = _tools
        response = await asyncio.to_thread(_agent.messages.create, **kwargs)
        return _extract_text(response)

    # Async callable: async def agent(input: str) -> str
    if callable(_agent) and asyncio.iscoroutinefunction(_agent):
        return await _agent(input_data)

    # Object with async run() method
    if hasattr(_agent, "run") and asyncio.iscoroutinefunction(_agent.run):
        return await _agent.run(input_data)

    msg = (
        "Loaded agent object is not a supported type. "
        "Expected: anthropic.AsyncAnthropic, anthropic.Anthropic, "
        "async callable, or object with async run() method."
    )
    raise TypeError(msg)


def _extract_text(response: Any) -> str:
    """Extract the first text content block from an Anthropic messages response."""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""
