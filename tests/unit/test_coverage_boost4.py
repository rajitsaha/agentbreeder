"""Coverage boost tests — iteration 2.

Covers:
  - registry/a2a_agents.py  (status filter in list, all-fields update)
  - api/routes/builders.py  (cache hit, missing schema, empty body, no-name import, duplicate)
  - api/services/audit_service.py  (filter combos, lineage string-model path, tool/prompt deps)
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.models.database import Base

_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
_SessionFactory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def session():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with _SessionFactory() as s:
        yield s
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ─────────────────────────────────────────────────────────────
# registry/a2a_agents.py — status filter + full update
# ─────────────────────────────────────────────────────────────


class TestA2AAgentRegistryBranches:
    @pytest.mark.asyncio
    async def test_list_with_status_filter(self, session: AsyncSession) -> None:
        from api.models.enums import A2AStatus
        from registry.a2a_agents import A2AAgentRegistry

        await A2AAgentRegistry.create(session, name="reg-agent", endpoint_url="http://a1")
        a2 = await A2AAgentRegistry.create(
            session, name="inactive-agent", endpoint_url="http://a2"
        )
        # Agents default to "registered" — set one to inactive
        a2.status = A2AStatus.inactive
        await session.flush()

        registered, total = await A2AAgentRegistry.list(session, status=A2AStatus.registered)
        assert total == 1
        assert registered[0].name == "reg-agent"

    @pytest.mark.asyncio
    async def test_list_with_team_and_status_filter(self, session: AsyncSession) -> None:
        from registry.a2a_agents import A2AAgentRegistry

        await A2AAgentRegistry.create(
            session, name="eng-agent", endpoint_url="http://e1", team="engineering"
        )
        await A2AAgentRegistry.create(
            session, name="ops-agent", endpoint_url="http://o1", team="ops"
        )

        results, total = await A2AAgentRegistry.list(session, team="engineering")
        assert total == 1
        assert results[0].name == "eng-agent"

    @pytest.mark.asyncio
    async def test_update_all_fields(self, session: AsyncSession) -> None:
        from api.models.enums import A2AStatus
        from registry.a2a_agents import A2AAgentRegistry

        agent = await A2AAgentRegistry.create(
            session,
            name="full-update",
            endpoint_url="http://original",
            capabilities=["chat"],
            auth_scheme="none",
        )

        updated = await A2AAgentRegistry.update(
            session,
            str(agent.id),
            endpoint_url="http://updated",
            agent_card={"version": "2"},
            capabilities=["chat", "stream"],
            auth_scheme="bearer",
            status=A2AStatus.inactive,
        )

        assert updated is not None
        assert updated.endpoint_url == "http://updated"
        assert updated.agent_card == {"version": "2"}
        assert updated.capabilities == ["chat", "stream"]
        assert updated.auth_scheme == "bearer"
        assert updated.status == A2AStatus.inactive

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self, session: AsyncSession) -> None:
        from registry.a2a_agents import A2AAgentRegistry

        result = await A2AAgentRegistry.update(
            session, "00000000-0000-0000-0000-000000000000", endpoint_url="http://x"
        )
        assert result is None


# ─────────────────────────────────────────────────────────────
# api/routes/builders.py — uncovered branches
# ─────────────────────────────────────────────────────────────


VALID_AGENT_YAML = textwrap.dedent("""\
    name: cache-test-agent
    version: "1.0.0"
    team: engineering
    owner: alice@example.com
    framework: langgraph
    model:
      primary: claude-sonnet-4
    deploy:
      cloud: aws
""")

VALID_AGENT_YAML_NO_NAME = textwrap.dedent("""\
    version: "1.0.0"
    team: engineering
    owner: alice@example.com
    framework: langgraph
    model:
      primary: claude-sonnet-4
    deploy:
      cloud: aws
""")


class TestBuildersBranchCoverage:
    """Hit the uncovered branches in api/routes/builders.py."""

    def setup_method(self):
        from fastapi.testclient import TestClient

        from api.main import app
        from api.routes.builders import _SCHEMA_CACHE, _STORE

        self.client = TestClient(app)
        self._store = _STORE
        self._cache = _SCHEMA_CACHE
        # Clear state
        for k in _STORE:
            _STORE[k].clear()
        _SCHEMA_CACHE.clear()

    def test_schema_cache_hit(self):
        """Second PUT to same resource_type uses cached schema (line 40)."""
        # First PUT — loads schema from disk, caches it
        resp1 = self.client.put(
            "/api/v1/builders/agent/cache-test/yaml",
            content=VALID_AGENT_YAML,
            headers={"content-type": "application/x-yaml"},
        )
        assert resp1.status_code == 200

        # Second PUT — hits _SCHEMA_CACHE branch
        resp2 = self.client.put(
            "/api/v1/builders/agent/cache-test2/yaml",
            content=VALID_AGENT_YAML.replace("cache-test-agent", "cache-test-agent2"),
            headers={"content-type": "application/x-yaml"},
        )
        assert resp2.status_code == 200

    def test_invalid_resource_type_put(self):
        """PUT with unknown resource_type raises 400."""
        resp = self.client.put(
            "/api/v1/builders/unknown-type/foo/yaml",
            content=VALID_AGENT_YAML,
            headers={"content-type": "application/x-yaml"},
        )
        assert resp.status_code == 400
        assert "Invalid resource_type" in resp.json()["detail"]

    def test_empty_body_raises_422(self):
        """PUT with empty YAML body raises 422 (line 168)."""
        resp = self.client.put(
            "/api/v1/builders/agent/empty-test/yaml",
            content="   ",
            headers={"content-type": "application/x-yaml"},
        )
        assert resp.status_code == 422
        assert "Empty YAML body" in resp.json()["detail"]

    def test_import_yaml_missing_name_field(self):
        """Import YAML without 'name' field raises 422 (line 201)."""
        resp = self.client.post(
            "/api/v1/builders/import",
            json={"resource_type": "agent", "yaml_content": VALID_AGENT_YAML_NO_NAME},
        )
        assert resp.status_code == 422
        assert "name" in resp.json()["detail"].lower()

    def test_import_yaml_duplicate_raises_409(self):
        """Import same name twice raises 409 (line 204)."""
        resp1 = self.client.post(
            "/api/v1/builders/import",
            json={"resource_type": "agent", "yaml_content": VALID_AGENT_YAML},
        )
        assert resp1.status_code == 201

        resp2 = self.client.post(
            "/api/v1/builders/import",
            json={"resource_type": "agent", "yaml_content": VALID_AGENT_YAML},
        )
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"]

    def test_invalid_resource_type_import(self):
        """Import with unknown resource_type raises 400."""
        resp = self.client.post(
            "/api/v1/builders/import",
            json={"resource_type": "widget", "yaml_content": VALID_AGENT_YAML},
        )
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────
# api/services/audit_service.py — filter combos & lineage deps
# ─────────────────────────────────────────────────────────────


class TestAuditServiceFilterBranches:
    """Cover the multiple filter branches in AuditService.list_events."""

    def setup_method(self):
        from api.services.audit_service import AuditService

        AuditService.reset()
        self.svc = AuditService

    @pytest.mark.asyncio
    async def test_filter_by_actor(self):
        from api.services.audit_service import AuditService

        await AuditService.log_event(
            actor="alice@example.com",
            action="deploy",
            resource_type="agent",
            resource_name="my-agent",
            team="eng",
        )
        await AuditService.log_event(
            actor="bob@example.com",
            action="delete",
            resource_type="agent",
            resource_name="other-agent",
            team="eng",
        )

        events, total = await AuditService.list_events(actor="alice")
        assert total == 1
        assert events[0].actor == "alice@example.com"

    @pytest.mark.asyncio
    async def test_filter_by_action(self):
        from api.services.audit_service import AuditService

        await AuditService.log_event(
            actor="alice@example.com",
            action="deploy",
            resource_type="agent",
            resource_name="a1",
            team="eng",
        )
        await AuditService.log_event(
            actor="bob@example.com",
            action="delete",
            resource_type="agent",
            resource_name="a2",
            team="eng",
        )

        events, total = await AuditService.list_events(action="deploy")
        assert total == 1
        assert events[0].action == "deploy"

    @pytest.mark.asyncio
    async def test_filter_by_resource_type(self):
        from api.services.audit_service import AuditService

        await AuditService.log_event(
            actor="alice@example.com",
            action="create",
            resource_type="prompt",
            resource_name="p1",
            team="eng",
        )
        await AuditService.log_event(
            actor="alice@example.com",
            action="create",
            resource_type="agent",
            resource_name="a1",
            team="eng",
        )

        events, total = await AuditService.list_events(resource_type="prompt")
        assert total == 1
        assert events[0].resource_type == "prompt"

    @pytest.mark.asyncio
    async def test_filter_by_resource_name(self):
        from api.services.audit_service import AuditService

        await AuditService.log_event(
            actor="alice@example.com",
            action="create",
            resource_type="agent",
            resource_name="prod-agent",
            team="eng",
        )
        await AuditService.log_event(
            actor="alice@example.com",
            action="create",
            resource_type="agent",
            resource_name="staging-agent",
            team="eng",
        )

        events, total = await AuditService.list_events(resource_name="prod")
        assert total == 1
        assert "prod" in events[0].resource_name

    @pytest.mark.asyncio
    async def test_filter_by_team(self):
        from api.services.audit_service import AuditService

        await AuditService.log_event(
            actor="alice@example.com",
            action="deploy",
            resource_type="agent",
            resource_name="a1",
            team="engineering",
        )
        await AuditService.log_event(
            actor="bob@example.com",
            action="deploy",
            resource_type="agent",
            resource_name="a2",
            team="ops",
        )

        events, total = await AuditService.list_events(team="engineering")
        assert total == 1

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self):
        from api.services.audit_service import AuditService

        await AuditService.log_event(
            actor="alice@example.com",
            action="deploy",
            resource_type="agent",
            resource_name="a1",
            team="eng",
        )

        now = datetime.now(UTC)
        # date_from before now → should match
        events, total = await AuditService.list_events(
            date_from=now - timedelta(minutes=1),
            date_to=now + timedelta(minutes=1),
        )
        assert total == 1

        # date_from in future → no match
        events2, total2 = await AuditService.list_events(
            date_from=now + timedelta(hours=1),
        )
        assert total2 == 0

    @pytest.mark.asyncio
    async def test_filter_by_date_to_only(self):
        from api.services.audit_service import AuditService

        await AuditService.log_event(
            actor="alice@example.com",
            action="deploy",
            resource_type="agent",
            resource_name="a1",
            team="eng",
        )

        # date_to in past → no match
        past = datetime.now(UTC) - timedelta(hours=1)
        events, total = await AuditService.list_events(date_to=past)
        assert total == 0


class TestAuditServiceLineageBranches:
    """Cover lineage dependency tracking branches (lines 395-475)."""

    def setup_method(self):
        from api.services.audit_service import AuditService

        AuditService.reset()

    @pytest.mark.asyncio
    async def test_track_string_model_dependency(self):
        """Cover the isinstance(model_cfg, str) branch."""
        from api.services.audit_service import AuditService

        config = {
            "model": "claude-sonnet-4",  # string, not dict
            "tools": [],
            "knowledge_bases": [],
            "prompts": {},
        }
        deps = await AuditService.sync_agent_dependencies(
            agent_name="test-agent",
            config_snapshot=config,
        )
        assert any(d.target_id == "claude-sonnet-4" for d in deps)

    @pytest.mark.asyncio
    async def test_track_dict_model_with_fallback(self):
        """Cover the dict model with fallback key."""
        from api.services.audit_service import AuditService

        config = {
            "model": {"primary": "gpt-4o", "fallback": "claude-3"},
            "tools": [],
            "knowledge_bases": [],
            "prompts": {},
        }
        deps = await AuditService.sync_agent_dependencies(
            agent_name="test-agent-2",
            config_snapshot=config,
        )
        model_deps = [d for d in deps if d.dependency_type == "uses_model"]
        assert len(model_deps) == 2  # primary + fallback

    @pytest.mark.asyncio
    async def test_track_string_tool_dependency(self):
        """Cover the isinstance(tool, str) branch in tools loop."""
        from api.services.audit_service import AuditService

        config = {
            "model": "claude-3",
            "tools": ["tools/zendesk-mcp", "tools/slack"],  # string tools
            "knowledge_bases": [],
            "prompts": {},
        }
        deps = await AuditService.sync_agent_dependencies(
            agent_name="test-agent-3",
            config_snapshot=config,
        )
        tool_deps = [d for d in deps if d.dependency_type == "uses_tool"]
        assert len(tool_deps) == 2

    @pytest.mark.asyncio
    async def test_track_dict_tool_without_ref(self):
        """Cover the dict tool branch where ref is empty (skipped)."""
        from api.services.audit_service import AuditService

        config = {
            "model": "claude-3",
            "tools": [{"name": ""}],  # empty ref/name — skipped
            "knowledge_bases": [],
            "prompts": {},
        }
        deps = await AuditService.sync_agent_dependencies(
            agent_name="test-agent-4",
            config_snapshot=config,
        )
        tool_deps = [d for d in deps if d.dependency_type == "uses_tool"]
        assert len(tool_deps) == 0

    @pytest.mark.asyncio
    async def test_track_prompt_dependencies(self):
        """Cover the prompts dict branch."""
        from api.services.audit_service import AuditService

        config = {
            "model": "claude-3",
            "tools": [],
            "knowledge_bases": [],
            "prompts": {"system": "prompts/support-v3", "user": "simple string"},
        }
        deps = await AuditService.sync_agent_dependencies(
            agent_name="test-agent-5",
            config_snapshot=config,
        )
        prompt_deps = [d for d in deps if d.dependency_type == "uses_prompt"]
        # Only "prompts/support-v3" has "/" so only 1 dep
        assert len(prompt_deps) == 1
        assert prompt_deps[0].target_name == "support-v3"
