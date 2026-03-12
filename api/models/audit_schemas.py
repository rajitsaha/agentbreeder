"""Pydantic schemas for Audit & Lineage API (M17)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Audit Event schemas
# ---------------------------------------------------------------------------


class AuditEventCreate(BaseModel):
    actor: str
    action: str
    resource_type: str
    resource_id: str | None = None
    resource_name: str
    team: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    actor: str
    actor_id: uuid.UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None
    resource_name: str
    team: str | None
    details: dict[str, Any]
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditEventFilter(BaseModel):
    actor: str | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_name: str | None = None
    team: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


# ---------------------------------------------------------------------------
# Resource Dependency schemas
# ---------------------------------------------------------------------------


class ResourceDependencyCreate(BaseModel):
    source_type: str
    source_id: str
    source_name: str
    target_type: str
    target_id: str
    target_name: str
    dependency_type: str


class ResourceDependencyResponse(BaseModel):
    id: uuid.UUID
    source_type: str
    source_id: str
    source_name: str
    target_type: str
    target_id: str
    target_name: str
    dependency_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Lineage Graph schemas
# ---------------------------------------------------------------------------


class LineageNode(BaseModel):
    id: str
    name: str
    type: str
    status: str = "active"


class LineageEdge(BaseModel):
    source_id: str
    target_id: str
    dependency_type: str


class LineageGraphResponse(BaseModel):
    nodes: list[LineageNode] = Field(default_factory=list)
    edges: list[LineageEdge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Impact Analysis schemas
# ---------------------------------------------------------------------------


class AffectedAgent(BaseModel):
    name: str
    dependency_type: str


class ImpactAnalysisResponse(BaseModel):
    resource_name: str
    resource_type: str
    affected_agents: list[AffectedAgent] = Field(default_factory=list)
