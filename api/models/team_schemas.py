"""Pydantic schemas for Teams RBAC API."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


# --- Team Schemas ---


class TeamCreate(BaseModel):
    name: str
    display_name: str
    description: str = ""


class TeamUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None


class TeamMemberResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_name: str
    role: str
    joined_at: datetime


class TeamResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str
    member_count: int
    created_at: datetime


class TeamDetailResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str
    member_count: int
    members: list[TeamMemberResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# --- Member Schemas ---


class TeamMemberAdd(BaseModel):
    user_email: str
    role: str = "viewer"  # "admin" | "deployer" | "viewer"


class TeamMemberUpdate(BaseModel):
    role: str  # "admin" | "deployer" | "viewer"


# --- API Key Schemas ---


class TeamApiKeyCreate(BaseModel):
    provider: str
    api_key: str


class TeamApiKeyResponse(BaseModel):
    id: str
    provider: str
    key_hint: str
    created_by: str
    created_at: datetime


# --- Permission Check ---


class PermissionCheckResult(BaseModel):
    allowed: bool
    reason: str
