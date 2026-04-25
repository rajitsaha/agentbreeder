"""Tracing API routes — trace ingestion, listing, metrics, and search."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import get_current_user
from api.middleware.rbac import require_role
from api.models.database import User

from api.models.schemas import ApiMeta, ApiResponse
from api.models.tracing_schemas import (
    AgentMetricsSummary,
    SpanCreate,
    SpanResponse,
    TraceCreate,
    TraceDetailResponse,
    TraceResponse,
)
from api.services.tracing_service import get_tracing_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/traces", tags=["tracing"])


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------


@router.get("", response_model=ApiResponse[list[TraceResponse]])
async def list_traces(
    _user: User = Depends(get_current_user),
    agent_name: str | None = Query(None),
    status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    min_duration: int | None = Query(None, ge=0),
    min_cost: float | None = Query(None, ge=0),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ApiResponse[list[TraceResponse]]:
    """List traces with optional filtering and pagination."""
    store = get_tracing_store()

    if q:
        traces, total = store.search_traces(
            query=q,
            agent_name=agent_name,
            status=status,
            page=page,
            per_page=per_page,
        )
    else:
        traces, total = store.list_traces(
            agent_name=agent_name,
            status=status,
            date_from=date_from,
            date_to=date_to,
            min_duration=min_duration,
            min_cost=min_cost,
            page=page,
            per_page=per_page,
        )

    return ApiResponse(
        data=[TraceResponse(**t.to_dict()) for t in traces],
        meta=ApiMeta(page=page, per_page=per_page, total=total),
    )


@router.get("/metrics/{agent_name}", response_model=ApiResponse[AgentMetricsSummary])
async def get_agent_metrics(
    agent_name: str,
    _user: User = Depends(get_current_user),
    days: int = Query(7, ge=1, le=365),
) -> ApiResponse[AgentMetricsSummary]:
    """Get aggregated metrics for an agent."""
    store = get_tracing_store()
    metrics = store.get_agent_metrics(agent_name, days=days)
    return ApiResponse(data=AgentMetricsSummary(**metrics))


@router.get("/{trace_id}", response_model=ApiResponse[TraceDetailResponse])
async def get_trace(trace_id: str, _user: User = Depends(get_current_user)) -> ApiResponse[TraceDetailResponse]:
    """Get a trace with all its spans."""
    store = get_tracing_store()
    trace = store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    spans = store.get_trace_spans(trace_id)

    return ApiResponse(
        data=TraceDetailResponse(
            trace=TraceResponse(**trace.to_dict()),
            spans=[SpanResponse(**s.to_dict()) for s in spans],
        )
    )


@router.post("", response_model=ApiResponse[TraceResponse], status_code=201)
async def create_trace(body: TraceCreate, _user: User = Depends(get_current_user)) -> ApiResponse[TraceResponse]:
    """Create/ingest a new trace."""
    store = get_tracing_store()

    # Check for duplicate trace_id
    existing = store.get_trace(body.trace_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Trace with trace_id '{body.trace_id}' already exists",
        )

    trace = store.create_trace(
        trace_id=body.trace_id,
        agent_name=body.agent_name,
        agent_id=body.agent_id,
        status=body.status,
        duration_ms=body.duration_ms,
        total_tokens=body.total_tokens,
        input_tokens=body.input_tokens,
        output_tokens=body.output_tokens,
        cost_usd=body.cost_usd,
        model_name=body.model_name,
        input_preview=body.input_preview,
        output_preview=body.output_preview,
        error_message=body.error_message,
        metadata=body.metadata,
    )
    return ApiResponse(data=TraceResponse(**trace.to_dict()))


@router.post("/{trace_id}/spans", response_model=ApiResponse[SpanResponse], status_code=201)
async def create_span(trace_id: str, body: SpanCreate, _user: User = Depends(get_current_user)) -> ApiResponse[SpanResponse]:
    """Add a span to an existing trace."""
    store = get_tracing_store()

    trace = store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    try:
        span = store.create_span(
            trace_id=trace_id,
            span_id=body.span_id,
            name=body.name,
            span_type=body.span_type,
            parent_span_id=body.parent_span_id,
            status=body.status,
            duration_ms=body.duration_ms,
            input_data=body.input_data,
            output_data=body.output_data,
            model_name=body.model_name,
            input_tokens=body.input_tokens,
            output_tokens=body.output_tokens,
            cost_usd=body.cost_usd,
            metadata=body.metadata,
            started_at=body.started_at,
            ended_at=body.ended_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ApiResponse(data=SpanResponse(**span.to_dict()))


@router.delete("", response_model=ApiResponse[dict])
async def delete_traces(
    _user: User = Depends(require_role("admin")),
    before: str = Query(..., description="ISO datetime — delete traces created before this date"),
) -> ApiResponse[dict]:
    """Bulk delete traces created before the given date."""
    store = get_tracing_store()
    count = store.delete_traces(before)
    return ApiResponse(data={"deleted_count": count})
