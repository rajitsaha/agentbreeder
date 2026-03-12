"""SQLAlchemy models for agent tracing and observability.

These models represent the database schema for traces and spans.
Currently backed by the in-memory TracingStore; will migrate to
PostgreSQL when the real DB is connected.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from api.models.database import Base


class Trace(Base):
    """A single trace representing an end-to-end agent invocation."""

    __tablename__ = "traces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(128), unique=True, index=True, nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    agent_name = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False)  # success, error, timeout
    duration_ms = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    model_name = Column(String(255), nullable=True)
    input_preview = Column(Text, nullable=True)
    output_preview = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    spans = relationship("Span", back_populates="trace", cascade="all, delete-orphan")


class Span(Base):
    """A single span within a trace — e.g. an LLM call, tool execution, or agent step."""

    __tablename__ = "spans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(128), ForeignKey("traces.trace_id"), index=True, nullable=False)
    span_id = Column(String(128), unique=True, nullable=False)
    parent_span_id = Column(String(128), nullable=True)
    name = Column(String(255), nullable=False)
    span_type = Column(String(32), nullable=False)  # llm, tool, agent, retrieval, custom
    status = Column(String(32), nullable=False)  # success, error
    duration_ms = Column(Integer, nullable=False, default=0)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    model_name = Column(String(255), nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    metadata_ = Column("metadata", JSON, nullable=True, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    ended_at = Column(DateTime(timezone=True), nullable=True)

    trace = relationship("Trace", back_populates="spans")
