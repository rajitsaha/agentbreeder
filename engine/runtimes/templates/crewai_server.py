"""AgentBreeder server wrapper for CrewAI agents.

This file is copied into the agent container at build time.
It wraps any CrewAI crew as a FastAPI server with /invoke and /health endpoints.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentbreeder.agent")

app = FastAPI(
    title="AgentBreeder Agent",
    description="Deployed by AgentBreeder",
    version=os.getenv("AGENT_VERSION", "0.1.0"),
)


class InvokeRequest(BaseModel):
    input: dict[str, Any]
    config: dict[str, Any] | None = None


class InvokeResponse(BaseModel):
    output: Any
    metadata: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    agent_name: str
    version: str


def _load_agent() -> Any:
    """Dynamically load the CrewAI crew from crew.py or agent.py."""
    sys.path.insert(0, "/app")

    # Try crew.py first, then agent.py
    for module_name in ("crew", "agent"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue

        # Look for crew attr first, then agent, then app
        for attr_name in ("crew", "agent", "app"):
            if hasattr(module, attr_name):
                return getattr(module, attr_name)

    msg = (
        "Could not find a crew object in crew.py or agent.py. "
        "Export a Crew instance as 'crew', 'agent', or 'app'."
    )
    raise AttributeError(msg)


# Load crew at startup
_crew = None


@app.on_event("startup")
async def startup() -> None:
    global _crew  # noqa: PLW0603
    logger.info("Loading CrewAI crew...")
    _crew = _load_agent()
    logger.info("CrewAI crew loaded successfully")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy" if _crew is not None else "loading",
        agent_name=os.getenv("AGENT_NAME", "unknown"),
        version=os.getenv("AGENT_VERSION", "0.1.0"),
    )


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest) -> InvokeResponse:
    if _crew is None:
        raise HTTPException(status_code=503, detail="Crew not loaded yet")

    try:
        result = await _run_crew(request.input)
        return InvokeResponse(output=result)
    except Exception as e:
        logger.exception("Crew invocation failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _run_crew(input_data: dict[str, Any]) -> str:
    """Run the CrewAI crew, wrapping the synchronous kickoff in a thread."""
    if hasattr(_crew, "kickoff"):
        return await asyncio.to_thread(_crew.kickoff, inputs=input_data)
    else:
        msg = "Crew object does not have a kickoff method"
        raise TypeError(msg)
