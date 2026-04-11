"""Shared OpenTelemetry initialisation utility for AgentBreeder agent containers.

This module is copied into every agent container at build time alongside the
framework-specific server template.  It must never import OTel packages at
module level — the packages are only available when the container was deployed
with OPENTELEMETRY_ENDPOINT set.  Zero breakage is the contract: if the env
var is absent the function returns a no-op tracer and the agent runs normally.

Usage (inside server templates):
    from _tracing import init_tracing
    tracer = init_tracing()          # call once at startup
    with tracer.start_as_current_span("agent.invoke") as span:
        span.set_attribute("agent.name", AGENT_NAME)
        ...
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("agentbreeder.tracing")

# Standard span attribute names shared by all AgentBreeder runtimes.
ATTR_AGENT_NAME = "agent.name"
ATTR_AGENT_VERSION = "agent.version"
ATTR_AGENT_FRAMEWORK = "agent.framework"
ATTR_LLM_MODEL = "llm.model"
ATTR_LLM_TOKENS_IN = "llm.token_count.input"
ATTR_LLM_TOKENS_OUT = "llm.token_count.output"


def init_tracing() -> Any:
    """Initialise OTel tracing and return a tracer.

    When OPENTELEMETRY_ENDPOINT is set: configures a BatchSpanProcessor with
    an OTLPSpanExporter pointing at that endpoint.

    When OPENTELEMETRY_ENDPOINT is not set: returns a no-op tracer so the
    agent starts without any tracing dependency.
    """
    endpoint = os.getenv("OPENTELEMETRY_ENDPOINT")
    service_name = os.getenv("AGENT_NAME", "agentbreeder-agent")

    if not endpoint:
        return _noop_tracer()

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": os.getenv("AGENT_VERSION", "0.0.0"),
                "agentbreeder.framework": os.getenv("AGENT_FRAMEWORK", "unknown"),
            }
        )

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        tracer = trace.get_tracer(service_name)
        logger.info("OTel tracing initialised → %s", endpoint)
        return tracer

    except ImportError:
        logger.warning(
            "OPENTELEMETRY_ENDPOINT is set but opentelemetry-sdk is not installed. "
            "Tracing disabled. Add opentelemetry-sdk to your requirements.txt."
        )
        return _noop_tracer()
    except Exception as exc:
        logger.warning("Failed to initialise OTel tracing: %s — continuing without tracing.", exc)
        return _noop_tracer()


class _NoopSpan:
    """Minimal no-op span that satisfies the context-manager protocol."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: ARG002
        pass

    def record_exception(self, exc: Exception) -> None:  # noqa: ARG002
        pass

    def set_status(self, status: Any) -> None:  # noqa: ARG002
        pass

    def __enter__(self) -> _NoopSpan:
        return self

    def __exit__(self, *_: Any) -> None:
        pass


class _NoopTracer:
    """Minimal no-op tracer returned when OTel is not configured."""

    def start_as_current_span(self, name: str, **_kwargs: Any) -> _NoopSpan:  # noqa: ARG002
        return _NoopSpan()

    def start_span(self, name: str, **_kwargs: Any) -> _NoopSpan:  # noqa: ARG002
        return _NoopSpan()


def _noop_tracer() -> _NoopTracer:
    return _NoopTracer()
