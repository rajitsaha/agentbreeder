"""Tests for audit & lineage service — events, dependencies, lineage, impact analysis."""

from __future__ import annotations

import pytest

from api.services.audit_service import AuditService


@pytest.fixture(autouse=True)
def _reset_audit():
    """Clear the in-memory store before each test."""
    AuditService.reset()
    yield
    AuditService.reset()


# ---------------------------------------------------------------------------
# Audit Events
# ---------------------------------------------------------------------------


class TestLogEvent:
    @pytest.mark.asyncio
    async def test_log_event(self) -> None:
        event = await AuditService.log_event(
            actor="alice@example.com",
            action="deploy",
            resource_type="agent",
            resource_name="customer-support",
            resource_id="agent-123",
            team="engineering",
            details={"target": "aws-ecs"},
        )
        assert event.actor == "alice@example.com"
        assert event.action == "deploy"
        assert event.resource_type == "agent"
        assert event.resource_name == "customer-support"
        assert event.resource_id == "agent-123"
        assert event.team == "engineering"
        assert event.details == {"target": "aws-ecs"}
        assert event.id

    @pytest.mark.asyncio
    async def test_log_event_minimal(self) -> None:
        event = await AuditService.log_event(
            actor="system",
            action="create",
            resource_type="tool",
            resource_name="zendesk-mcp",
        )
        assert event.actor == "system"
        assert event.resource_id is None
        assert event.team is None
        assert event.details == {}


class TestListEventsWithFilters:
    @pytest.mark.asyncio
    async def test_list_events_empty(self) -> None:
        events, total = await AuditService.list_events()
        assert events == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_events_returns_all(self) -> None:
        await AuditService.log_event(
            actor="alice", action="create", resource_type="agent", resource_name="a1"
        )
        await AuditService.log_event(
            actor="bob", action="deploy", resource_type="agent", resource_name="a2"
        )
        events, total = await AuditService.list_events()
        assert total == 2
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_filter_by_actor(self) -> None:
        await AuditService.log_event(
            actor="alice", action="create", resource_type="agent", resource_name="a1"
        )
        await AuditService.log_event(
            actor="bob", action="deploy", resource_type="agent", resource_name="a2"
        )
        events, total = await AuditService.list_events(actor="alice")
        assert total == 1
        assert events[0].actor == "alice"

    @pytest.mark.asyncio
    async def test_filter_by_action(self) -> None:
        await AuditService.log_event(
            actor="alice", action="create", resource_type="agent", resource_name="a1"
        )
        await AuditService.log_event(
            actor="alice", action="deploy", resource_type="agent", resource_name="a2"
        )
        events, total = await AuditService.list_events(action="deploy")
        assert total == 1
        assert events[0].action == "deploy"

    @pytest.mark.asyncio
    async def test_filter_by_resource_type(self) -> None:
        await AuditService.log_event(
            actor="alice", action="create", resource_type="agent", resource_name="a1"
        )
        await AuditService.log_event(
            actor="alice", action="create", resource_type="tool", resource_name="t1"
        )
        events, total = await AuditService.list_events(resource_type="tool")
        assert total == 1
        assert events[0].resource_type == "tool"

    @pytest.mark.asyncio
    async def test_filter_by_team(self) -> None:
        await AuditService.log_event(
            actor="alice", action="create", resource_type="agent", resource_name="a1", team="eng"
        )
        await AuditService.log_event(
            actor="bob", action="create", resource_type="agent", resource_name="a2", team="sales"
        )
        events, total = await AuditService.list_events(team="eng")
        assert total == 1
        assert events[0].team == "eng"

    @pytest.mark.asyncio
    async def test_pagination(self) -> None:
        for i in range(5):
            await AuditService.log_event(
                actor="alice", action="create", resource_type="agent", resource_name=f"a{i}"
            )
        events, total = await AuditService.list_events(page=2, per_page=2)
        assert total == 5
        assert len(events) == 2


class TestEventsForResource:
    @pytest.mark.asyncio
    async def test_events_for_resource(self) -> None:
        await AuditService.log_event(
            actor="alice",
            action="create",
            resource_type="agent",
            resource_id="a-1",
            resource_name="agent-1",
        )
        await AuditService.log_event(
            actor="bob",
            action="deploy",
            resource_type="agent",
            resource_id="a-1",
            resource_name="agent-1",
        )
        await AuditService.log_event(
            actor="carol",
            action="create",
            resource_type="agent",
            resource_id="a-2",
            resource_name="agent-2",
        )
        events = await AuditService.get_events_for_resource("agent", "a-1")
        assert len(events) == 2
        assert all(e.resource_id == "a-1" for e in events)


class TestSearchEvents:
    @pytest.mark.asyncio
    async def test_search_events(self) -> None:
        await AuditService.log_event(
            actor="alice@example.com",
            action="deploy",
            resource_type="agent",
            resource_name="customer-support",
        )
        await AuditService.log_event(
            actor="bob@example.com",
            action="create",
            resource_type="tool",
            resource_name="zendesk-mcp",
        )
        results = await AuditService.search_events("customer")
        assert len(results) == 1
        assert results[0].resource_name == "customer-support"

    @pytest.mark.asyncio
    async def test_search_by_actor(self) -> None:
        await AuditService.log_event(
            actor="alice@example.com",
            action="deploy",
            resource_type="agent",
            resource_name="a1",
        )
        results = await AuditService.search_events("alice")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_by_action(self) -> None:
        await AuditService.log_event(
            actor="alice",
            action="deploy",
            resource_type="agent",
            resource_name="a1",
        )
        results = await AuditService.search_events("deploy")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class TestRegisterDependency:
    @pytest.mark.asyncio
    async def test_register_dependency(self) -> None:
        dep = await AuditService.register_dependency(
            source_type="agent",
            source_id="agent-1",
            source_name="customer-support",
            target_type="tool",
            target_id="zendesk-mcp",
            target_name="zendesk-mcp",
            dependency_type="uses_tool",
        )
        assert dep.source_type == "agent"
        assert dep.target_type == "tool"
        assert dep.dependency_type == "uses_tool"
        assert dep.id

    @pytest.mark.asyncio
    async def test_register_dependency_upsert(self) -> None:
        """Re-registering the same edge should update, not duplicate."""
        await AuditService.register_dependency(
            source_type="agent",
            source_id="a1",
            source_name="a1",
            target_type="tool",
            target_id="t1",
            target_name="t1",
            dependency_type="uses_tool",
        )
        await AuditService.register_dependency(
            source_type="agent",
            source_id="a1",
            source_name="a1-updated",
            target_type="tool",
            target_id="t1",
            target_name="t1",
            dependency_type="uses_tool",
        )
        assert len(AuditService._dependencies) == 1
        assert AuditService._dependencies[0].source_name == "a1-updated"

    @pytest.mark.asyncio
    async def test_remove_dependency(self) -> None:
        await AuditService.register_dependency(
            source_type="agent",
            source_id="a1",
            source_name="a1",
            target_type="tool",
            target_id="t1",
            target_name="t1",
            dependency_type="uses_tool",
        )
        removed = await AuditService.remove_dependency("agent", "a1", "tool", "t1")
        assert removed is True
        assert len(AuditService._dependencies) == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_dependency(self) -> None:
        removed = await AuditService.remove_dependency("agent", "a1", "tool", "t1")
        assert removed is False


# ---------------------------------------------------------------------------
# Lineage Graph
# ---------------------------------------------------------------------------


class TestGetLineageGraph:
    @pytest.mark.asyncio
    async def test_get_lineage_graph(self) -> None:
        # Agent depends on tool and model
        await AuditService.register_dependency(
            source_type="agent",
            source_id="a1",
            source_name="my-agent",
            target_type="tool",
            target_id="t1",
            target_name="zendesk-mcp",
            dependency_type="uses_tool",
        )
        await AuditService.register_dependency(
            source_type="agent",
            source_id="a1",
            source_name="my-agent",
            target_type="model",
            target_id="m1",
            target_name="claude-sonnet-4",
            dependency_type="uses_model",
        )

        graph = await AuditService.get_lineage_graph("agent", "a1")
        assert len(graph.nodes) == 3  # agent + tool + model
        assert len(graph.edges) == 2

        node_ids = {n.id for n in graph.nodes}
        assert "a1" in node_ids
        assert "t1" in node_ids
        assert "m1" in node_ids

    @pytest.mark.asyncio
    async def test_lineage_graph_bidirectional(self) -> None:
        """Graph should include both incoming and outgoing edges."""
        # agent-1 uses tool-1
        await AuditService.register_dependency(
            source_type="agent",
            source_id="a1",
            source_name="agent-1",
            target_type="tool",
            target_id="t1",
            target_name="tool-1",
            dependency_type="uses_tool",
        )
        # agent-2 also uses tool-1
        await AuditService.register_dependency(
            source_type="agent",
            source_id="a2",
            source_name="agent-2",
            target_type="tool",
            target_id="t1",
            target_name="tool-1",
            dependency_type="uses_tool",
        )

        # Lineage from tool-1 perspective
        graph = await AuditService.get_lineage_graph("tool", "t1")
        assert len(graph.nodes) == 3  # tool + 2 agents
        assert len(graph.edges) == 2

    @pytest.mark.asyncio
    async def test_lineage_graph_empty(self) -> None:
        graph = await AuditService.get_lineage_graph("agent", "nonexistent")
        assert len(graph.nodes) == 1  # just the root node
        assert len(graph.edges) == 0


# ---------------------------------------------------------------------------
# Impact Analysis
# ---------------------------------------------------------------------------


class TestImpactAnalysis:
    @pytest.mark.asyncio
    async def test_impact_analysis(self) -> None:
        await AuditService.register_dependency(
            source_type="agent",
            source_id="a1",
            source_name="agent-1",
            target_type="tool",
            target_id="t1",
            target_name="zendesk-mcp",
            dependency_type="uses_tool",
        )
        await AuditService.register_dependency(
            source_type="agent",
            source_id="a2",
            source_name="agent-2",
            target_type="tool",
            target_id="t1",
            target_name="zendesk-mcp",
            dependency_type="uses_tool",
        )

        analysis = await AuditService.get_impact_analysis("tool", "zendesk-mcp")
        assert analysis.resource_name == "zendesk-mcp"
        assert analysis.resource_type == "tool"
        assert len(analysis.affected_agents) == 2
        agent_names = {a.name for a in analysis.affected_agents}
        assert "agent-1" in agent_names
        assert "agent-2" in agent_names

    @pytest.mark.asyncio
    async def test_impact_analysis_no_dependents(self) -> None:
        analysis = await AuditService.get_impact_analysis("tool", "unused-tool")
        assert len(analysis.affected_agents) == 0


# ---------------------------------------------------------------------------
# Sync Agent Dependencies
# ---------------------------------------------------------------------------


class TestSyncAgentDependencies:
    @pytest.mark.asyncio
    async def test_sync_agent_dependencies(self) -> None:
        config = {
            "name": "customer-support",
            "model": {
                "primary": "claude-sonnet-4",
                "fallback": "gpt-4o",
            },
            "tools": [
                {"ref": "tools/zendesk-mcp"},
                {"ref": "tools/order-lookup"},
            ],
            "prompts": {
                "system": "prompts/support-system-v3",
            },
            "knowledge_bases": [
                {"ref": "kb/product-docs"},
            ],
        }

        deps = await AuditService.sync_agent_dependencies("customer-support", config)

        # Should register: 2 models + 2 tools + 1 prompt + 1 KB = 6
        assert len(deps) == 6

        dep_types = [d.dependency_type for d in deps]
        assert dep_types.count("uses_model") == 2
        assert dep_types.count("uses_tool") == 2
        assert dep_types.count("uses_prompt") == 1
        assert dep_types.count("uses_kb") == 1

    @pytest.mark.asyncio
    async def test_sync_with_memory(self) -> None:
        config = {
            "name": "agent-with-memory",
            "model": {"primary": "claude-sonnet-4"},
            "memory": "shared-memory-config",
        }
        deps = await AuditService.sync_agent_dependencies("agent-with-memory", config)
        mem_deps = [d for d in deps if d.dependency_type == "uses_memory"]
        assert len(mem_deps) == 1
        assert mem_deps[0].target_name == "shared-memory-config"

    @pytest.mark.asyncio
    async def test_sync_minimal_config(self) -> None:
        config = {"name": "bare-agent", "model": {"primary": "gpt-4o"}}
        deps = await AuditService.sync_agent_dependencies("bare-agent", config)
        assert len(deps) == 1
        assert deps[0].dependency_type == "uses_model"


# ---------------------------------------------------------------------------
# Audit Immutability
# ---------------------------------------------------------------------------


class TestAuditImmutability:
    @pytest.mark.asyncio
    async def test_audit_immutability(self) -> None:
        """Events cannot be deleted from the store via public API."""
        await AuditService.log_event(
            actor="alice",
            action="deploy",
            resource_type="agent",
            resource_name="my-agent",
        )
        # There is no delete method on the service
        assert not hasattr(AuditService, "delete_event")
        assert not hasattr(AuditService, "remove_event")

        # Events persist
        events, total = await AuditService.list_events()
        assert total == 1

    @pytest.mark.asyncio
    async def test_events_are_append_only(self) -> None:
        """New events are always appended; the store only grows."""
        for i in range(3):
            await AuditService.log_event(
                actor="alice",
                action="create",
                resource_type="agent",
                resource_name=f"agent-{i}",
            )
        _, total = await AuditService.list_events()
        assert total == 3

        # Add one more
        await AuditService.log_event(
            actor="bob",
            action="deploy",
            resource_type="agent",
            resource_name="agent-3",
        )
        _, total = await AuditService.list_events()
        assert total == 4
