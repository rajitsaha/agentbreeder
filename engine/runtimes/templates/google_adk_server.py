"""AgentBreeder server wrapper for Google ADK agents.

This file is copied into the agent container at build time.
It wraps any Google ADK agent as a FastAPI server with /invoke and /health endpoints.

Authentication: uses Application Default Credentials (ADC).
Set GOOGLE_APPLICATION_CREDENTIALS to a service account key path, or rely on
Workload Identity when running on GCP.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentbreeder.agent")

# Module-level globals — initialized at startup
_agent = None
_runner = None


def _load_agent() -> Any:
    """Dynamically load the ADK agent from agent.py."""
    sys.path.insert(0, "/app")
    try:
        module = importlib.import_module("agent")
    except ImportError as e:
        logger.error("Failed to import agent module: %s", e)
        raise

    # Look for common Google ADK exports
    for attr_name in ("root_agent", "agent", "app"):
        if hasattr(module, attr_name):
            return getattr(module, attr_name)

    msg = (
        "agent.py must export one of: 'root_agent', 'agent', or 'app'. "
        "This should be a google.adk.agents.Agent instance."
    )
    raise AttributeError(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """FastAPI lifespan context manager for startup and shutdown."""
    global _agent, _runner  # noqa: PLW0603
    logger.info("Loading Google ADK agent...")
    _agent = _load_agent()

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    app_name = os.getenv("GOOGLE_CLOUD_PROJECT", "agentbreeder-local")
    _runner = Runner(
        agent=_agent,
        app_name=app_name,
        session_service=InMemorySessionService(),
    )
    logger.info("Google ADK agent loaded successfully (app_name=%s)", app_name)

    yield
    # shutdown code (if needed in the future)


app = FastAPI(
    title="AgentBreeder Agent",
    description="Deployed by AgentBreeder",
    version=os.getenv("AGENT_VERSION", "0.1.0"),
    lifespan=lifespan,
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


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy" if _agent is not None else "loading",
        agent_name=os.getenv("AGENT_NAME", "unknown"),
        version=os.getenv("AGENT_VERSION", "0.1.0"),
    )


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest) -> InvokeResponse:
    if _agent is None or _runner is None:
        raise HTTPException(status_code=503, detail="Agent not loaded yet")

    try:
        result = await _run_agent(request.input, request.config or {})
        return InvokeResponse(output=result)
    except Exception as e:
        logger.exception("Agent invocation failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _run_agent(input_text: str, config: dict[str, Any]) -> str:
    """Run the Google ADK agent and return the final response text."""
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types

    # Use a per-request session so invocations are independent
    session_service = InMemorySessionService()
    app_name = os.getenv("GOOGLE_CLOUD_PROJECT", "agentbreeder-local")
    user_id = config.get("user_id", "agentbreeder-user")
    session = await session_service.create_session(app_name=app_name, user_id=user_id)

    from google.adk.runners import Runner

    runner = Runner(
        agent=_agent,
        app_name=app_name,
        session_service=session_service,
    )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=input_text)],
    )

    final_response = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_response += part.text

    return final_response
