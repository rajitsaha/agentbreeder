"""Pydantic schemas for tracing request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# --- Trace Schemas ---


class TraceCreate(BaseModel):
    """Request body for creating/ingesting a trace."""

    trace_id: str
    agent_id: str | None = None
    agent_name: str
    status: str = "success"  # success, error, timeout
    duration_ms: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model_name: str | None = None
    input_preview: str | None = None
    output_preview: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpanCreate(BaseModel):
    """Request body for creating a span within a trace."""

    span_id: str
    parent_span_id: str | None = None
    name: str
    span_type: str = "custom"  # llm, tool, agent, retrieval, custom
    status: str = "success"  # success, error
    duration_ms: int = 0
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    model_name: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: str | None = None
    ended_at: str | None = None


class SpanResponse(BaseModel):
    """Response for a single span."""

    id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    span_type: str
    status: str
    duration_ms: int
    input_data: dict[str, Any] | None
    output_data: dict[str, Any] | None
    model_name: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    metadata: dict[str, Any]
    started_at: str
    ended_at: str | None
    children: list[SpanResponse] = Field(default_factory=list)


class TraceResponse(BaseModel):
    """Response for a single trace (list view, no spans)."""

    id: str
    trace_id: str
    agent_id: str | None
    agent_name: str
    status: str
    duration_ms: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model_name: str | None
    input_preview: str | None
    output_preview: str | None
    error_message: str | None
    metadata: dict[str, Any]
    created_at: str


class TraceDetailResponse(BaseModel):
    """Response for a single trace with all its spans."""

    trace: TraceResponse
    spans: list[SpanResponse]


class TraceFilterParams(BaseModel):
    """Filter parameters for listing traces."""

    agent_name: str | None = None
    status: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    min_duration: int | None = None
    min_cost: float | None = None


class AgentMetricsSummary(BaseModel):
    """Aggregated metrics for an agent."""

    agent_name: str
    request_count: int = 0
    error_count: int = 0
    avg_duration_ms: float = 0.0
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    period_days: int = 7
