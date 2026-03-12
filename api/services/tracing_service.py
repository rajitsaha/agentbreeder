"""Tracing Service — In-memory store for traces and spans.

Provides:
- CRUD for traces and spans
- Filtering and pagination
- Agent-level metrics aggregation
- Search across traces
- Trace timeline (span tree) construction
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class SpanData:
    """In-memory representation of a span."""

    id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str = ""
    span_type: str = "custom"
    status: str = "success"
    duration_ms: int = 0
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    model_name: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    ended_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "span_type": self.span_type,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "model_name": self.model_name,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "metadata": self.metadata,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "children": [],
        }


@dataclass
class TraceData:
    """In-memory representation of a trace."""

    id: str
    trace_id: str
    agent_id: str | None = None
    agent_name: str = ""
    status: str = "success"
    duration_ms: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model_name: str | None = None
    input_preview: str | None = None
    output_preview: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "model_name": self.model_name,
            "input_preview": self.input_preview,
            "output_preview": self.output_preview,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# In-Memory Store
# ---------------------------------------------------------------------------


class TracingStore:
    """In-memory store for traces and spans.

    This will be replaced by PostgreSQL when the real DB is connected.
    """

    def __init__(self) -> None:
        self._traces: dict[str, TraceData] = {}  # trace_id -> TraceData
        self._spans: dict[str, list[SpanData]] = {}  # trace_id -> list of SpanData

    # --- Trace CRUD ---

    def create_trace(
        self,
        trace_id: str,
        agent_name: str,
        agent_id: str | None = None,
        status: str = "success",
        duration_ms: int = 0,
        total_tokens: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        model_name: str | None = None,
        input_preview: str | None = None,
        output_preview: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceData:
        """Create a new trace."""
        now = datetime.now(UTC).isoformat()

        # Truncate previews to 200 chars
        if input_preview and len(input_preview) > 200:
            input_preview = input_preview[:200]
        if output_preview and len(output_preview) > 200:
            output_preview = output_preview[:200]

        trace = TraceData(
            id=str(uuid.uuid4()),
            trace_id=trace_id,
            agent_id=agent_id,
            agent_name=agent_name,
            status=status,
            duration_ms=duration_ms,
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            model_name=model_name,
            input_preview=input_preview,
            output_preview=output_preview,
            error_message=error_message,
            metadata=metadata or {},
            created_at=now,
        )
        self._traces[trace_id] = trace
        self._spans[trace_id] = []
        logger.info("Created trace %s for agent %s", trace_id, agent_name)
        return trace

    def get_trace(self, trace_id: str) -> TraceData | None:
        """Get a trace by trace_id."""
        return self._traces.get(trace_id)

    def get_trace_spans(self, trace_id: str) -> list[SpanData]:
        """Get all spans for a trace."""
        return self._spans.get(trace_id, [])

    def list_traces(
        self,
        agent_name: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_duration: int | None = None,
        min_cost: float | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[TraceData], int]:
        """List traces with filtering and pagination."""
        traces = sorted(
            self._traces.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )

        # Apply filters
        if agent_name:
            traces = [t for t in traces if t.agent_name == agent_name]
        if status:
            traces = [t for t in traces if t.status == status]
        if date_from:
            traces = [t for t in traces if t.created_at >= date_from]
        if date_to:
            traces = [t for t in traces if t.created_at <= date_to]
        if min_duration is not None:
            traces = [t for t in traces if t.duration_ms >= min_duration]
        if min_cost is not None:
            traces = [t for t in traces if t.cost_usd >= min_cost]

        total = len(traces)
        start = (page - 1) * per_page
        end = start + per_page
        return traces[start:end], total

    def delete_traces(self, before_date: str) -> int:
        """Delete traces created before the given date. Returns count of deleted traces."""
        to_delete = [tid for tid, t in self._traces.items() if t.created_at < before_date]
        for tid in to_delete:
            del self._traces[tid]
            self._spans.pop(tid, None)

        logger.info("Deleted %d traces before %s", len(to_delete), before_date)
        return len(to_delete)

    # --- Span CRUD ---

    def create_span(
        self,
        trace_id: str,
        span_id: str,
        name: str,
        span_type: str = "custom",
        parent_span_id: str | None = None,
        status: str = "success",
        duration_ms: int = 0,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        model_name: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        metadata: dict[str, Any] | None = None,
        started_at: str | None = None,
        ended_at: str | None = None,
    ) -> SpanData:
        """Create a new span within a trace."""
        if trace_id not in self._traces:
            raise ValueError(f"Trace {trace_id} not found")

        now = datetime.now(UTC).isoformat()
        span = SpanData(
            id=str(uuid.uuid4()),
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            span_type=span_type,
            status=status,
            duration_ms=duration_ms,
            input_data=input_data,
            output_data=output_data,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            metadata=metadata or {},
            started_at=started_at or now,
            ended_at=ended_at,
        )
        self._spans[trace_id].append(span)
        logger.info("Created span %s (%s) in trace %s", span_id, name, trace_id)
        return span

    # --- Metrics ---

    def get_agent_metrics(
        self,
        agent_name: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Compute aggregated metrics for an agent over the last N days."""
        # In production this would use proper datetime math with cutoff filtering
        traces = [t for t in self._traces.values() if t.agent_name == agent_name]

        if not traces:
            return {
                "agent_name": agent_name,
                "request_count": 0,
                "error_count": 0,
                "avg_duration_ms": 0.0,
                "p50_duration_ms": 0.0,
                "p95_duration_ms": 0.0,
                "p99_duration_ms": 0.0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "period_days": days,
            }

        durations = sorted([t.duration_ms for t in traces])
        error_count = sum(1 for t in traces if t.status == "error")
        total_tokens = sum(t.total_tokens for t in traces)
        total_cost = sum(t.cost_usd for t in traces)

        return {
            "agent_name": agent_name,
            "request_count": len(traces),
            "error_count": error_count,
            "avg_duration_ms": round(sum(durations) / len(durations), 1),
            "p50_duration_ms": _percentile(durations, 50),
            "p95_duration_ms": _percentile(durations, 95),
            "p99_duration_ms": _percentile(durations, 99),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "period_days": days,
        }

    # --- Search ---

    def search_traces(
        self,
        query: str,
        agent_name: str | None = None,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[TraceData], int]:
        """Search traces by query string across multiple fields."""
        query_lower = query.lower()
        results: list[TraceData] = []

        for trace in self._traces.values():
            # Apply additional filters first
            if agent_name and trace.agent_name != agent_name:
                continue
            if status and trace.status != status:
                continue

            # Search across text fields
            searchable = " ".join(
                filter(
                    None,
                    [
                        trace.agent_name,
                        trace.input_preview,
                        trace.output_preview,
                        trace.error_message,
                        trace.model_name,
                        trace.trace_id,
                    ],
                )
            ).lower()

            if query_lower in searchable:
                results.append(trace)

        results.sort(key=lambda t: t.created_at, reverse=True)
        total = len(results)
        start = (page - 1) * per_page
        end = start + per_page
        return results[start:end], total

    # --- Timeline ---

    def get_trace_timeline(self, trace_id: str) -> list[dict[str, Any]]:
        """Get spans as an ordered tree based on parent_span_id.

        Returns a list of root spans, each with a 'children' key containing nested spans.
        """
        spans = self._spans.get(trace_id, [])
        if not spans:
            return []

        # Build lookup
        span_dicts: dict[str, dict[str, Any]] = {}
        for span in sorted(spans, key=lambda s: s.started_at):
            d = span.to_dict()
            d["children"] = []
            span_dicts[span.span_id] = d

        # Build tree
        roots: list[dict[str, Any]] = []
        for span in sorted(spans, key=lambda s: s.started_at):
            d = span_dicts[span.span_id]
            if span.parent_span_id and span.parent_span_id in span_dicts:
                span_dicts[span.parent_span_id]["children"].append(d)
            else:
                roots.append(d)

        return roots


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile(sorted_values: list[int], pct: float) -> float:
    """Compute percentile from a sorted list of values."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    if n == 1:
        return float(sorted_values[0])
    idx = (pct / 100.0) * (n - 1)
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    if lower == upper:
        return float(sorted_values[lower])
    frac = idx - lower
    return round(sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac, 1)


# ---------------------------------------------------------------------------
# Global Singleton
# ---------------------------------------------------------------------------


_store: TracingStore | None = None


def get_tracing_store() -> TracingStore:
    """Get the global tracing store singleton."""
    global _store
    if _store is None:
        _store = TracingStore()
    return _store
