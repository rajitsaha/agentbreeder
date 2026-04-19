"""Grafana observability connector — pushes AgentBreeder metrics via remote_write."""

from __future__ import annotations

import logging
import time
from typing import Any

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class GrafanaConnector(BaseConnector):
    """Connector for Grafana — discovers dashboards and pushes metrics/traces.

    Supports:
    - Availability check via the Grafana health endpoint
    - Scanning existing Grafana dashboards into the AgentBreeder registry
    - Pushing agent metrics via Grafana Loki push API (JSON log streams)
    - Pushing distributed traces to Grafana Tempo in OTLP JSON format
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        org_id: str = "1",
    ) -> None:
        # Strip trailing slash for consistent URL construction
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._org_id = org_id

    @property
    def name(self) -> str:
        return "grafana"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Scope-OrgID": self._org_id,
        }

    async def is_available(self) -> bool:
        """Check if the Grafana instance is reachable."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._endpoint}/api/health",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except httpx.HTTPError as exc:
            logger.warning("Grafana availability check failed: %s", exc)
            return False

    async def scan(self) -> list[dict]:
        """Discover Grafana dashboards and return them as registry items."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._endpoint}/api/search",
                    params={"type": "dash-db"},
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    logger.warning("Grafana dashboard scan returned %d", resp.status_code)
                    return []
                dashboards: list[dict[str, Any]] = resp.json()
                return [
                    {
                        "name": d["title"],
                        "description": "",
                        "source": "grafana",
                        "type": "dashboard",
                        "url": d.get("url", ""),
                    }
                    for d in dashboards
                ]
        except httpx.HTTPError as exc:
            logger.error("Grafana scan failed: %s", exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error during Grafana scan: %s", exc)
            return []

    async def push_metrics(self, events: list[dict]) -> None:
        """Push agent metrics to Grafana via the Loki push API.

        Uses the Loki JSON push format — each metric event becomes a log line
        with structured labels, compatible with Grafana's LogQL and metric queries.
        """
        import httpx

        if not events:
            return

        now_ns = str(int(time.time() * 1e9))

        # Group events by agent label for efficient Loki streams
        streams: dict[str, list[list[str]]] = {}
        for event in events:
            agent = event.get("agent", "unknown")
            env = event.get("env", "production")
            metric = event.get("metric", "invocation")
            value = event.get("value", 1)
            label_key = f'{{source="agentbreeder",agent="{agent}",env="{env}",metric="{metric}"}}'
            log_line = f'metric="{metric}" value={value} agent="{agent}" env="{env}"'
            streams.setdefault(label_key, []).append([now_ns, log_line])

        payload = {
            "streams": [
                {"stream": _parse_label_selector(key), "values": values}
                for key, values in streams.items()
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._endpoint}/api/v1/push",
                    headers=self._headers(),
                    json=payload,
                )
                if resp.status_code not in (200, 204):
                    logger.warning(
                        "Grafana Loki push returned %d: %s",
                        resp.status_code,
                        resp.text,
                    )
                else:
                    logger.debug("Pushed %d metric events to Grafana Loki", len(events))
        except httpx.HTTPError as exc:
            logger.error("Grafana push_metrics failed: %s", exc)

    async def push_traces(self, traces: list[dict]) -> None:
        """Push distributed traces to Grafana Tempo in OTLP JSON format."""
        import httpx

        if not traces:
            return

        # Build OTLP-compatible JSON payload
        spans = []
        for trace in traces:
            start_ns = int(trace.get("start_time", time.time()) * 1e9)
            duration_ns = int(trace.get("duration_ms", 0) * 1e6)
            end_ns = start_ns + duration_ns

            span: dict[str, Any] = {
                "traceId": _to_hex(trace.get("trace_id", int(time.time() * 1e9))),
                "spanId": _to_hex(trace.get("span_id", int(time.time() * 1e9)), width=16),
                "name": trace.get("name", "agentbreeder.agent.invoke"),
                "kind": 2,  # SPAN_KIND_SERVER
                "startTimeUnixNano": str(start_ns),
                "endTimeUnixNano": str(end_ns),
                "status": {"code": 2 if trace.get("error") else 1},
                "attributes": [
                    {"key": "agent", "value": {"stringValue": trace.get("agent", "unknown")}},
                    {
                        "key": "framework",
                        "value": {"stringValue": trace.get("framework", "unknown")},
                    },
                    {"key": "env", "value": {"stringValue": trace.get("env", "production")}},
                    {"key": "service.name", "value": {"stringValue": "agentbreeder"}},
                ],
            }

            if trace.get("parent_span_id"):
                span["parentSpanId"] = _to_hex(trace["parent_span_id"], width=16)

            spans.append(span)

        otlp_payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": "agentbreeder"},
                            }
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "agentbreeder.connector.grafana"},
                            "spans": spans,
                        }
                    ],
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._endpoint}/api/traces",
                    headers=self._headers(),
                    json=otlp_payload,
                )
                if resp.status_code not in (200, 202, 204):
                    logger.warning(
                        "Grafana Tempo push returned %d: %s",
                        resp.status_code,
                        resp.text,
                    )
                else:
                    logger.debug("Pushed %d traces to Grafana Tempo", len(traces))
        except httpx.HTTPError as exc:
            logger.error("Grafana push_traces failed: %s", exc)


def _parse_label_selector(selector: str) -> dict[str, str]:
    """Parse a Loki label selector string into a dict."""
    # e.g. '{source="agentbreeder",agent="foo"}' → {"source": "agentbreeder", "agent": "foo"}
    result: dict[str, str] = {}
    inner = selector.strip("{} ")
    for pair in inner.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip().strip('"')
    return result


def _to_hex(value: int, width: int = 32) -> str:
    """Convert an integer to a zero-padded hex string (for trace/span IDs)."""
    return format(abs(value) & ((1 << (width * 4)) - 1), f"0{width}x")
