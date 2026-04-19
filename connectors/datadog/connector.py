"""Datadog observability connector — pushes AgentBreeder metrics to Datadog APM."""

from __future__ import annotations

import logging
import time
from typing import Any

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class DatadogConnector(BaseConnector):
    """Connector for Datadog APM — discovers monitors and pushes metrics/traces.

    Supports:
    - Availability check via the Datadog API validate endpoint
    - Scanning existing Datadog monitors into the AgentBreeder registry
    - Pushing agent invocation metrics as Datadog series points
    - Pushing distributed traces as Datadog APM trace spans
    """

    def __init__(
        self,
        api_key: str,
        app_key: str = "",
        site: str = "datadoghq.com",
    ) -> None:
        self._api_key = api_key
        self._app_key = app_key
        self._site = site
        self._base_url = f"https://api.{site}"

    @property
    def name(self) -> str:
        return "datadog"

    def _headers(self) -> dict[str, str]:
        headers = {"DD-API-KEY": self._api_key, "Content-Type": "application/json"}
        if self._app_key:
            headers["DD-APPLICATION-KEY"] = self._app_key
        return headers

    async def is_available(self) -> bool:
        """Check if Datadog API is reachable and the API key is valid."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/validate",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except httpx.HTTPError as exc:
            logger.warning("Datadog availability check failed: %s", exc)
            return False

    async def scan(self) -> list[dict]:
        """Discover Datadog monitors and return them as registry items."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/monitor",
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    logger.warning("Datadog monitor scan returned %d", resp.status_code)
                    return []
                monitors: list[dict[str, Any]] = resp.json()
                return [
                    {
                        "name": m["name"],
                        "description": m.get("message", ""),
                        "source": "datadog",
                        "type": "monitor",
                    }
                    for m in monitors
                ]
        except httpx.HTTPError as exc:
            logger.error("Datadog scan failed: %s", exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error during Datadog scan: %s", exc)
            return []

    async def push_metrics(self, events: list[dict]) -> None:
        """Push agent invocation events to Datadog as metric series points."""
        import httpx

        if not events:
            return

        now = int(time.time())
        series = [
            {
                "metric": f"agentbreeder.agent.{event.get('metric', 'invocation')}",
                "type": 0,  # UNSPECIFIED — Datadog will infer gauge
                "points": [
                    {
                        "timestamp": event.get("timestamp", now),
                        "value": float(event.get("value", 1)),
                    }
                ],
                "tags": [
                    f"agent:{event.get('agent', 'unknown')}",
                    f"env:{event.get('env', 'production')}",
                ],
                "resources": [{"name": "agentbreeder", "type": "host"}],
            }
            for event in events
        ]

        payload = {"series": series}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/v2/series",
                    headers=self._headers(),
                    json=payload,
                )
                if resp.status_code not in (202, 200):
                    logger.warning(
                        "Datadog metrics push returned %d: %s",
                        resp.status_code,
                        resp.text,
                    )
                else:
                    logger.debug("Pushed %d metric events to Datadog", len(events))
        except httpx.HTTPError as exc:
            logger.error("Datadog push_metrics failed: %s", exc)

    async def push_traces(self, traces: list[dict]) -> None:
        """Push distributed traces to Datadog APM."""
        import httpx

        if not traces:
            return

        # Datadog traces API expects a list of trace lists (each trace is a list of spans)
        dd_traces = []
        for trace in traces:
            trace_id = trace.get("trace_id", int(time.time() * 1e9) & 0xFFFFFFFFFFFFFFFF)
            span_id = trace.get("span_id", int(time.time() * 1e9) & 0xFFFFFFFFFFFFFFFF)
            start_ns = int(trace.get("start_time", time.time()) * 1e9)
            duration_ns = int(trace.get("duration_ms", 0) * 1e6)

            span = {
                "trace_id": trace_id,
                "span_id": span_id,
                "name": trace.get("name", "agentbreeder.agent.invoke"),
                "resource": trace.get("resource", trace.get("agent", "unknown")),
                "service": "agentbreeder",
                "type": "web",
                "start": start_ns,
                "duration": duration_ns,
                "error": 1 if trace.get("error") else 0,
                "meta": {
                    "agent": trace.get("agent", "unknown"),
                    "framework": trace.get("framework", "unknown"),
                    "env": trace.get("env", "production"),
                },
            }
            dd_traces.append([span])

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.put(
                    f"{self._base_url}/api/v0.2/traces",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json=dd_traces,
                )
                if resp.status_code not in (200, 202):
                    logger.warning(
                        "Datadog traces push returned %d: %s",
                        resp.status_code,
                        resp.text,
                    )
                else:
                    logger.debug("Pushed %d traces to Datadog APM", len(traces))
        except httpx.HTTPError as exc:
            logger.error("Datadog push_traces failed: %s", exc)
