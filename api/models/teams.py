"""SQLAlchemy models for Teams, TeamMembership, and TeamApiKey.

These are the ORM definitions for M15: RBAC & Teams.
Currently backed by in-memory stores (see team_service.py) — the models
here serve as the canonical schema for when the real DB is connected.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from api.models.database import Base


class Team(Base):  # type: ignore[misc]
    __tablename__ = "teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(String, default="", server_default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class TeamMembership(Base):  # type: ignore[misc]
    __tablename__ = "team_memberships"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_user"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String, nullable=False)  # "admin", "deployer", "viewer"
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class TeamApiKey(Base):  # type: ignore[misc]
    __tablename__ = "team_api_keys"
    __table_args__ = (UniqueConstraint("team_id", "provider", name="uq_team_provider"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String, nullable=False)  # "openai", "anthropic", etc.
    encrypted_key = Column(String, nullable=False)  # Fernet-encrypted
    key_hint = Column(String, nullable=False)  # last 4 chars: "...abcd"
    created_by = Column(String, nullable=False)  # email
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
