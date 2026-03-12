"""Audit & Lineage service — in-memory store for audit events and resource dependencies.

Provides immutable audit logging, dependency tracking, lineage graph building,
and impact analysis for all registry resources.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal data models
# ---------------------------------------------------------------------------


class AuditEventRecord(BaseModel):
    """An immutable audit event."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    actor: str
    actor_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    resource_name: str
    team: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResourceDependencyRecord(BaseModel):
    """A dependency edge between two resources."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_type: str
    source_id: str
    source_name: str
    target_type: str
    target_id: str
    target_name: str
    dependency_type: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LineageNode(BaseModel):
    id: str
    name: str
    type: str
    status: str = "active"


class LineageEdge(BaseModel):
    source_id: str
    target_id: str
    dependency_type: str


class LineageGraph(BaseModel):
    nodes: list[LineageNode] = Field(default_factory=list)
    edges: list[LineageEdge] = Field(default_factory=list)


class AffectedAgent(BaseModel):
    name: str
    dependency_type: str


class ImpactAnalysis(BaseModel):
    resource_name: str
    resource_type: str
    affected_agents: list[AffectedAgent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AuditService:
    """In-memory audit & lineage service."""

    # Storage
    _events: list[AuditEventRecord] = []
    _dependencies: list[ResourceDependencyRecord] = []

    @classmethod
    def reset(cls) -> None:
        """Clear all in-memory data (used by tests)."""
        cls._events = []
        cls._dependencies = []

    # -- Audit events -------------------------------------------------------

    @classmethod
    async def log_event(
        cls,
        *,
        actor: str,
        action: str,
        resource_type: str,
        resource_name: str,
        resource_id: str | None = None,
        team: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditEventRecord:
        """Record an immutable audit event."""
        event = AuditEventRecord(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            team=team,
            details=details or {},
            ip_address=ip_address,
        )
        cls._events.append(event)
        logger.info(
            "Audit: %s %s %s/%s",
            actor,
            action,
            resource_type,
            resource_name,
        )
        return event

    @classmethod
    async def list_events(
        cls,
        *,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_name: str | None = None,
        team: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[AuditEventRecord], int]:
        """List audit events with filtering and pagination."""
        filtered = list(cls._events)

        if actor:
            filtered = [e for e in filtered if actor.lower() in e.actor.lower()]
        if action:
            filtered = [e for e in filtered if e.action == action]
        if resource_type:
            filtered = [e for e in filtered if e.resource_type == resource_type]
        if resource_name:
            filtered = [e for e in filtered if resource_name.lower() in e.resource_name.lower()]
        if team:
            filtered = [e for e in filtered if e.team and team.lower() in e.team.lower()]
        if date_from:
            filtered = [e for e in filtered if e.created_at >= date_from]
        if date_to:
            filtered = [e for e in filtered if e.created_at <= date_to]

        # Sort newest first
        filtered.sort(key=lambda e: e.created_at, reverse=True)

        total = len(filtered)
        start = (page - 1) * per_page
        end = start + per_page
        return filtered[start:end], total

    @classmethod
    async def get_events_for_resource(
        cls,
        resource_type: str,
        resource_id: str,
    ) -> list[AuditEventRecord]:
        """Get all events for a specific resource."""
        return sorted(
            [
                e
                for e in cls._events
                if e.resource_type == resource_type and e.resource_id == resource_id
            ],
            key=lambda e: e.created_at,
            reverse=True,
        )

    @classmethod
    async def search_events(cls, query: str) -> list[AuditEventRecord]:
        """Full-text search across actor, resource_name, and action."""
        q = query.lower()
        results = [
            e
            for e in cls._events
            if q in e.actor.lower() or q in e.resource_name.lower() or q in e.action.lower()
        ]
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results

    # -- Dependencies -------------------------------------------------------

    @classmethod
    async def register_dependency(
        cls,
        *,
        source_type: str,
        source_id: str,
        source_name: str,
        target_type: str,
        target_id: str,
        target_name: str,
        dependency_type: str,
    ) -> ResourceDependencyRecord:
        """Register a dependency between two resources. Upserts on unique key."""
        # Check for existing
        for dep in cls._dependencies:
            if (
                dep.source_type == source_type
                and dep.source_id == source_id
                and dep.target_type == target_type
                and dep.target_id == target_id
            ):
                # Update existing
                dep.target_name = target_name
                dep.source_name = source_name
                dep.dependency_type = dependency_type
                return dep

        dep = ResourceDependencyRecord(
            source_type=source_type,
            source_id=source_id,
            source_name=source_name,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            dependency_type=dependency_type,
        )
        cls._dependencies.append(dep)
        return dep

    @classmethod
    async def remove_dependency(
        cls,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
    ) -> bool:
        """Remove a specific dependency edge."""
        before = len(cls._dependencies)
        cls._dependencies = [
            d
            for d in cls._dependencies
            if not (
                d.source_type == source_type
                and d.source_id == source_id
                and d.target_type == target_type
                and d.target_id == target_id
            )
        ]
        return len(cls._dependencies) < before

    @classmethod
    async def get_lineage_graph(
        cls,
        resource_type: str,
        resource_id: str,
    ) -> LineageGraph:
        """Build a full dependency graph for a resource, walking both directions."""
        nodes: dict[str, LineageNode] = {}
        edges: list[LineageEdge] = []

        # Add the root node
        root_key = f"{resource_type}:{resource_id}"
        root_name = resource_id
        # Try to find name from dependencies
        for d in cls._dependencies:
            if d.source_type == resource_type and d.source_id == resource_id:
                root_name = d.source_name
                break
            if d.target_type == resource_type and d.target_id == resource_id:
                root_name = d.target_name
                break
        nodes[root_key] = LineageNode(id=resource_id, name=root_name, type=resource_type)

        # Walk outgoing: this resource depends on ...
        for d in cls._dependencies:
            if d.source_type == resource_type and d.source_id == resource_id:
                target_key = f"{d.target_type}:{d.target_id}"
                if target_key not in nodes:
                    nodes[target_key] = LineageNode(
                        id=d.target_id, name=d.target_name, type=d.target_type
                    )
                edges.append(
                    LineageEdge(
                        source_id=d.source_id,
                        target_id=d.target_id,
                        dependency_type=d.dependency_type,
                    )
                )

        # Walk incoming: resources that depend on this one
        for d in cls._dependencies:
            if d.target_type == resource_type and d.target_id == resource_id:
                source_key = f"{d.source_type}:{d.source_id}"
                if source_key not in nodes:
                    nodes[source_key] = LineageNode(
                        id=d.source_id, name=d.source_name, type=d.source_type
                    )
                edges.append(
                    LineageEdge(
                        source_id=d.source_id,
                        target_id=d.target_id,
                        dependency_type=d.dependency_type,
                    )
                )

        return LineageGraph(nodes=list(nodes.values()), edges=edges)

    @classmethod
    async def get_impact_analysis(
        cls,
        resource_type: str,
        resource_name: str,
    ) -> ImpactAnalysis:
        """Find all agents affected by a change to the given resource."""
        affected: list[AffectedAgent] = []
        seen: set[str] = set()

        for d in cls._dependencies:
            if (
                d.target_type == resource_type
                and d.target_name == resource_name
                and d.source_type == "agent"
            ):
                key = f"{d.source_name}:{d.dependency_type}"
                if key not in seen:
                    seen.add(key)
                    affected.append(
                        AffectedAgent(
                            name=d.source_name,
                            dependency_type=d.dependency_type,
                        )
                    )

        return ImpactAnalysis(
            resource_name=resource_name,
            resource_type=resource_type,
            affected_agents=affected,
        )

    @classmethod
    async def sync_agent_dependencies(
        cls,
        agent_name: str,
        config_snapshot: dict[str, Any],
    ) -> list[ResourceDependencyRecord]:
        """Parse an agent config snapshot and register all dependencies."""
        deps: list[ResourceDependencyRecord] = []
        agent_id = config_snapshot.get("name", agent_name)

        # Model dependency
        model_cfg = config_snapshot.get("model", {})
        if isinstance(model_cfg, dict):
            primary = model_cfg.get("primary")
            if primary:
                dep = await cls.register_dependency(
                    source_type="agent",
                    source_id=agent_id,
                    source_name=agent_name,
                    target_type="model",
                    target_id=primary,
                    target_name=primary,
                    dependency_type="uses_model",
                )
                deps.append(dep)
            fallback = model_cfg.get("fallback")
            if fallback:
                dep = await cls.register_dependency(
                    source_type="agent",
                    source_id=agent_id,
                    source_name=agent_name,
                    target_type="model",
                    target_id=fallback,
                    target_name=fallback,
                    dependency_type="uses_model",
                )
                deps.append(dep)
        elif isinstance(model_cfg, str):
            dep = await cls.register_dependency(
                source_type="agent",
                source_id=agent_id,
                source_name=agent_name,
                target_type="model",
                target_id=model_cfg,
                target_name=model_cfg,
                dependency_type="uses_model",
            )
            deps.append(dep)

        # Tool dependencies
        tools = config_snapshot.get("tools", [])
        if isinstance(tools, list):
            for tool in tools:
                if isinstance(tool, dict):
                    ref = tool.get("ref") or tool.get("name", "")
                    if ref:
                        tool_name = ref.split("/")[-1] if "/" in ref else ref
                        dep = await cls.register_dependency(
                            source_type="agent",
                            source_id=agent_id,
                            source_name=agent_name,
                            target_type="tool",
                            target_id=tool_name,
                            target_name=tool_name,
                            dependency_type="uses_tool",
                        )
                        deps.append(dep)
                elif isinstance(tool, str):
                    tool_name = tool.split("/")[-1] if "/" in tool else tool
                    dep = await cls.register_dependency(
                        source_type="agent",
                        source_id=agent_id,
                        source_name=agent_name,
                        target_type="tool",
                        target_id=tool_name,
                        target_name=tool_name,
                        dependency_type="uses_tool",
                    )
                    deps.append(dep)

        # Prompt dependencies
        prompts = config_snapshot.get("prompts", {})
        if isinstance(prompts, dict):
            for _key, val in prompts.items():
                if isinstance(val, str) and "/" in val:
                    prompt_name = val.split("/")[-1]
                    dep = await cls.register_dependency(
                        source_type="agent",
                        source_id=agent_id,
                        source_name=agent_name,
                        target_type="prompt",
                        target_id=prompt_name,
                        target_name=prompt_name,
                        dependency_type="uses_prompt",
                    )
                    deps.append(dep)

        # Knowledge base dependencies
        kbs = config_snapshot.get("knowledge_bases", [])
        if isinstance(kbs, list):
            for kb in kbs:
                if isinstance(kb, dict):
                    ref = kb.get("ref", "")
                    if ref:
                        kb_name = ref.split("/")[-1] if "/" in ref else ref
                        dep = await cls.register_dependency(
                            source_type="agent",
                            source_id=agent_id,
                            source_name=agent_name,
                            target_type="knowledge_base",
                            target_id=kb_name,
                            target_name=kb_name,
                            dependency_type="uses_kb",
                        )
                        deps.append(dep)

        # Memory dependency
        memory = config_snapshot.get("memory")
        if memory:
            mem_name = memory if isinstance(memory, str) else memory.get("ref", "memory")
            dep = await cls.register_dependency(
                source_type="agent",
                source_id=agent_id,
                source_name=agent_name,
                target_type="memory",
                target_id=mem_name,
                target_name=mem_name,
                dependency_type="uses_memory",
            )
            deps.append(dep)

        return deps
