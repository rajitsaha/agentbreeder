"""Audit & Lineage API routes (M17)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query

from api.models.audit_schemas import (
    AffectedAgent,
    AuditEventCreate,
    AuditEventResponse,
    ImpactAnalysisResponse,
    LineageEdge,
    LineageGraphResponse,
    LineageNode,
    ResourceDependencyCreate,
    ResourceDependencyResponse,
)
from api.models.schemas import ApiMeta, ApiResponse
from api.services.audit_service import AuditService

router = APIRouter(tags=["audit", "lineage"])


# ---------------------------------------------------------------------------
# Audit Events
# ---------------------------------------------------------------------------


@router.get("/api/v1/audit", response_model=ApiResponse[list[AuditEventResponse]])
async def list_audit_events(
    actor: str | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    resource_name: str | None = Query(None),
    team: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ApiResponse[list[AuditEventResponse]]:
    """List audit events with optional filters."""
    df: datetime | None = None
    dt: datetime | None = None
    if date_from:
        df = datetime.fromisoformat(date_from).replace(tzinfo=UTC)
    if date_to:
        dt = datetime.fromisoformat(date_to).replace(tzinfo=UTC)

    events, total = await AuditService.list_events(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_name=resource_name,
        team=team,
        date_from=df,
        date_to=dt,
        page=page,
        per_page=per_page,
    )
    return ApiResponse(
        data=[AuditEventResponse.model_validate(e.model_dump()) for e in events],
        meta=ApiMeta(page=page, per_page=per_page, total=total),
    )


@router.get(
    "/api/v1/audit/resource/{resource_type}/{resource_id}",
    response_model=ApiResponse[list[AuditEventResponse]],
)
async def get_events_for_resource(
    resource_type: str,
    resource_id: str,
) -> ApiResponse[list[AuditEventResponse]]:
    """Get all audit events for a specific resource."""
    events = await AuditService.get_events_for_resource(resource_type, resource_id)
    return ApiResponse(
        data=[AuditEventResponse.model_validate(e.model_dump()) for e in events],
        meta=ApiMeta(total=len(events)),
    )


@router.post(
    "/api/v1/audit",
    response_model=ApiResponse[AuditEventResponse],
    status_code=201,
)
async def record_audit_event(
    body: AuditEventCreate,
) -> ApiResponse[AuditEventResponse]:
    """Record a new audit event (internal use)."""
    event = await AuditService.log_event(
        actor=body.actor,
        action=body.action,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        resource_name=body.resource_name,
        team=body.team,
        details=body.details,
    )
    return ApiResponse(data=AuditEventResponse.model_validate(event.model_dump()))


# ---------------------------------------------------------------------------
# Lineage & Dependencies
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/lineage/{resource_type}/{resource_id}",
    response_model=ApiResponse[LineageGraphResponse],
)
async def get_lineage_graph(
    resource_type: str,
    resource_id: str,
) -> ApiResponse[LineageGraphResponse]:
    """Get the dependency graph for a resource."""
    graph = await AuditService.get_lineage_graph(resource_type, resource_id)
    return ApiResponse(
        data=LineageGraphResponse(
            nodes=[LineageNode.model_validate(n.model_dump()) for n in graph.nodes],
            edges=[LineageEdge.model_validate(e.model_dump()) for e in graph.edges],
        )
    )


@router.get(
    "/api/v1/lineage/impact/{resource_type}/{resource_name}",
    response_model=ApiResponse[ImpactAnalysisResponse],
)
async def get_impact_analysis(
    resource_type: str,
    resource_name: str,
) -> ApiResponse[ImpactAnalysisResponse]:
    """Analyze the impact of changing a resource on dependent agents."""
    analysis = await AuditService.get_impact_analysis(resource_type, resource_name)
    return ApiResponse(
        data=ImpactAnalysisResponse(
            resource_name=analysis.resource_name,
            resource_type=analysis.resource_type,
            affected_agents=[
                AffectedAgent(name=a.name, dependency_type=a.dependency_type)
                for a in analysis.affected_agents
            ],
        )
    )


@router.post(
    "/api/v1/lineage/dependencies",
    response_model=ApiResponse[ResourceDependencyResponse],
    status_code=201,
)
async def register_dependency(
    body: ResourceDependencyCreate,
) -> ApiResponse[ResourceDependencyResponse]:
    """Register a dependency between two resources."""
    dep = await AuditService.register_dependency(
        source_type=body.source_type,
        source_id=body.source_id,
        source_name=body.source_name,
        target_type=body.target_type,
        target_id=body.target_id,
        target_name=body.target_name,
        dependency_type=body.dependency_type,
    )
    return ApiResponse(data=ResourceDependencyResponse.model_validate(dep.model_dump()))


@router.post(
    "/api/v1/lineage/sync/{agent_name}",
    response_model=ApiResponse[list[ResourceDependencyResponse]],
)
async def sync_agent_dependencies(
    agent_name: str,
    config_snapshot: dict,
) -> ApiResponse[list[ResourceDependencyResponse]]:
    """Sync agent dependencies from its config snapshot."""
    deps = await AuditService.sync_agent_dependencies(agent_name, config_snapshot)
    return ApiResponse(
        data=[ResourceDependencyResponse.model_validate(d.model_dump()) for d in deps],
        meta=ApiMeta(total=len(deps)),
    )
