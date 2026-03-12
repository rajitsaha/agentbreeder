"""Tests for team service — CRUD, memberships, RBAC permissions, API key encryption."""

from __future__ import annotations

import pytest

from api.services.team_service import TeamService, _decrypt_key, _encrypt_key


@pytest.fixture(autouse=True)
def _reset_teams():
    """Clear the in-memory store before each test."""
    TeamService.reset()
    yield
    TeamService.reset()


# ---------------------------------------------------------------------------
# Team CRUD
# ---------------------------------------------------------------------------


class TestTeamCRUD:
    @pytest.mark.asyncio
    async def test_create_team(self) -> None:
        team = await TeamService.create_team(
            name="engineering",
            display_name="Engineering",
            description="The eng team",
        )
        assert team.name == "engineering"
        assert team.display_name == "Engineering"
        assert team.description == "The eng team"
        assert team.id

    @pytest.mark.asyncio
    async def test_create_team_duplicate_name(self) -> None:
        await TeamService.create_team(name="eng", display_name="Eng")
        with pytest.raises(ValueError, match="already exists"):
            await TeamService.create_team(name="eng", display_name="Eng 2")

    @pytest.mark.asyncio
    async def test_list_teams(self) -> None:
        await TeamService.create_team(name="beta", display_name="Beta")
        await TeamService.create_team(name="alpha", display_name="Alpha")
        teams, total = await TeamService.list_teams()
        assert total == 2
        assert teams[0].name == "alpha"  # sorted by name

    @pytest.mark.asyncio
    async def test_get_team(self) -> None:
        team = await TeamService.create_team(name="test", display_name="Test")
        fetched = await TeamService.get_team(team.id)
        assert fetched is not None
        assert fetched.name == "test"

    @pytest.mark.asyncio
    async def test_update_team(self) -> None:
        team = await TeamService.create_team(name="test", display_name="Test")
        updated = await TeamService.update_team(team.id, display_name="Updated")
        assert updated is not None
        assert updated.display_name == "Updated"

    @pytest.mark.asyncio
    async def test_delete_team(self) -> None:
        team = await TeamService.create_team(name="to-delete", display_name="Delete Me")
        assert await TeamService.delete_team(team.id) is True
        assert await TeamService.get_team(team.id) is None

    @pytest.mark.asyncio
    async def test_delete_team_not_found(self) -> None:
        assert await TeamService.delete_team("nonexistent") is False


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


class TestMembers:
    @pytest.mark.asyncio
    async def test_add_member(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        member = await TeamService.add_member(
            team.id,
            user_id="user-1",
            user_email="alice@co.com",
            user_name="Alice",
            role="deployer",
        )
        assert member.role == "deployer"
        assert member.user_email == "alice@co.com"
        assert member.team_id == team.id

    @pytest.mark.asyncio
    async def test_add_member_duplicate(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        await TeamService.add_member(
            team.id, user_id="user-1", user_email="a@co.com", user_name="A"
        )
        with pytest.raises(ValueError, match="already a member"):
            await TeamService.add_member(
                team.id, user_id="user-1", user_email="a@co.com", user_name="A"
            )

    @pytest.mark.asyncio
    async def test_add_member_invalid_role(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        with pytest.raises(ValueError, match="Invalid role"):
            await TeamService.add_member(
                team.id,
                user_id="user-1",
                user_email="a@co.com",
                user_name="A",
                role="superadmin",
            )

    @pytest.mark.asyncio
    async def test_remove_member(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        await TeamService.add_member(
            team.id, user_id="user-1", user_email="a@co.com", user_name="A"
        )
        assert await TeamService.remove_member(team.id, "user-1") is True
        members = await TeamService.get_team_members(team.id)
        assert len(members) == 0

    @pytest.mark.asyncio
    async def test_remove_member_not_found(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        assert await TeamService.remove_member(team.id, "ghost") is False

    @pytest.mark.asyncio
    async def test_update_member_role(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        await TeamService.add_member(
            team.id, user_id="user-1", user_email="a@co.com", user_name="A", role="viewer"
        )
        updated = await TeamService.update_member_role(team.id, "user-1", "admin")
        assert updated is not None
        assert updated.role == "admin"

    @pytest.mark.asyncio
    async def test_get_team_members(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        await TeamService.add_member(team.id, user_id="u1", user_email="b@co.com", user_name="Bob")
        await TeamService.add_member(
            team.id, user_id="u2", user_email="a@co.com", user_name="Alice"
        )
        members = await TeamService.get_team_members(team.id)
        assert len(members) == 2
        # Sorted by name
        assert members[0].user_name == "Alice"
        assert members[1].user_name == "Bob"


# ---------------------------------------------------------------------------
# Permission checks
# ---------------------------------------------------------------------------


class TestPermissions:
    @pytest.mark.asyncio
    async def test_permission_check_admin(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        await TeamService.add_member(
            team.id,
            user_id="admin-1",
            user_email="admin@co.com",
            user_name="Admin",
            role="admin",
        )
        # Admin can do anything
        for action in ["read", "create", "deploy", "update", "delete", "manage"]:
            allowed, reason = await TeamService.can_user_do(
                "admin-1", action, resource_team=team.id
            )
            assert allowed, f"Admin should be able to {action}: {reason}"

    @pytest.mark.asyncio
    async def test_permission_check_deployer(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        await TeamService.add_member(
            team.id,
            user_id="dep-1",
            user_email="dep@co.com",
            user_name="Deployer",
            role="deployer",
        )
        # Deployer can read, create, deploy, update
        for action in ["read", "create", "deploy", "update"]:
            allowed, _ = await TeamService.can_user_do("dep-1", action, resource_team=team.id)
            assert allowed, f"Deployer should be able to {action}"

        # Deployer cannot delete or manage
        for action in ["delete", "manage"]:
            allowed, _ = await TeamService.can_user_do("dep-1", action, resource_team=team.id)
            assert not allowed, f"Deployer should NOT be able to {action}"

    @pytest.mark.asyncio
    async def test_permission_check_viewer(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        await TeamService.add_member(
            team.id,
            user_id="view-1",
            user_email="view@co.com",
            user_name="Viewer",
            role="viewer",
        )
        # Viewer can only read
        allowed, _ = await TeamService.can_user_do("view-1", "read", resource_team=team.id)
        assert allowed

        for action in ["create", "deploy", "update", "delete", "manage"]:
            allowed, _ = await TeamService.can_user_do("view-1", action, resource_team=team.id)
            assert not allowed, f"Viewer should NOT be able to {action}"

    @pytest.mark.asyncio
    async def test_cross_team_access_denied(self) -> None:
        team_a = await TeamService.create_team(name="team-a", display_name="A")
        team_b = await TeamService.create_team(name="team-b", display_name="B")
        await TeamService.add_member(
            team_a.id,
            user_id="user-a",
            user_email="a@co.com",
            user_name="UserA",
            role="deployer",
        )
        # User A is not a member of team B — should be denied
        allowed, reason = await TeamService.can_user_do("user-a", "read", resource_team=team_b.id)
        assert not allowed
        assert "not a member" in reason

    @pytest.mark.asyncio
    async def test_cross_team_admin_can_read(self) -> None:
        team_a = await TeamService.create_team(name="team-a", display_name="A")
        team_b = await TeamService.create_team(name="team-b", display_name="B")
        await TeamService.add_member(
            team_a.id,
            user_id="admin-a",
            user_email="admin@co.com",
            user_name="AdminA",
            role="admin",
        )
        # Admin of team A can read team B's resources (cross-team read)
        allowed, _ = await TeamService.can_user_do("admin-a", "read", resource_team=team_b.id)
        assert allowed

    @pytest.mark.asyncio
    async def test_unknown_action(self) -> None:
        allowed, reason = await TeamService.can_user_do("user-1", "fly")
        assert not allowed
        assert "Unknown action" in reason

    @pytest.mark.asyncio
    async def test_no_membership_denied(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        allowed, _ = await TeamService.can_user_do("stranger", "read", resource_team=team.id)
        assert not allowed


# ---------------------------------------------------------------------------
# API Key encryption
# ---------------------------------------------------------------------------


class TestApiKeys:
    @pytest.mark.asyncio
    async def test_api_key_encrypt_decrypt(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        key_data = await TeamService.set_api_key(
            team.id,
            provider="openai",
            api_key="sk-test-1234567890abcdef",
            created_by="admin@co.com",
        )
        assert key_data.key_hint == "...cdef"
        assert key_data.provider == "openai"

        # Decrypt and verify
        decrypted = await TeamService.get_decrypted_key(team.id, "openai")
        assert decrypted == "sk-test-1234567890abcdef"

    @pytest.mark.asyncio
    async def test_api_key_replace(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        await TeamService.set_api_key(
            team.id, provider="openai", api_key="sk-old", created_by="a@co.com"
        )
        await TeamService.set_api_key(
            team.id, provider="openai", api_key="sk-new-key", created_by="b@co.com"
        )
        keys = await TeamService.list_api_keys(team.id)
        assert len(keys) == 1
        assert keys[0].created_by == "b@co.com"
        decrypted = await TeamService.get_decrypted_key(team.id, "openai")
        assert decrypted == "sk-new-key"

    @pytest.mark.asyncio
    async def test_api_key_delete(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        key_data = await TeamService.set_api_key(
            team.id, provider="openai", api_key="sk-del", created_by="a@co.com"
        )
        assert await TeamService.delete_api_key(key_data.id) is True
        keys = await TeamService.list_api_keys(team.id)
        assert len(keys) == 0

    @pytest.mark.asyncio
    async def test_api_key_test(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        key_data = await TeamService.set_api_key(
            team.id,
            provider="anthropic",
            api_key="sk-ant-test1234",
            created_by="a@co.com",
        )
        result = await TeamService.test_api_key(key_data.id)
        assert result["success"] is True
        assert result["provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_api_key_test_not_found(self) -> None:
        result = await TeamService.test_api_key("nonexistent")
        assert result["success"] is False

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test the raw encrypt/decrypt functions."""
        original = "sk-secret-key-12345"
        encrypted = _encrypt_key(original)
        assert encrypted != original
        decrypted = _decrypt_key(encrypted)
        assert decrypted == original


# ---------------------------------------------------------------------------
# User teams
# ---------------------------------------------------------------------------


class TestUserTeams:
    @pytest.mark.asyncio
    async def test_list_user_teams(self) -> None:
        team_a = await TeamService.create_team(name="alpha", display_name="Alpha")
        team_b = await TeamService.create_team(name="beta", display_name="Beta")
        await TeamService.create_team(name="gamma", display_name="Gamma")

        await TeamService.add_member(
            team_a.id, user_id="user-1", user_email="u@co.com", user_name="U"
        )
        await TeamService.add_member(
            team_b.id, user_id="user-1", user_email="u@co.com", user_name="U"
        )

        teams = await TeamService.get_user_teams("user-1")
        assert len(teams) == 2
        names = [t.name for t in teams]
        assert "alpha" in names
        assert "beta" in names
        assert "gamma" not in names

    @pytest.mark.asyncio
    async def test_list_user_teams_empty(self) -> None:
        teams = await TeamService.get_user_teams("nobody")
        assert len(teams) == 0

    @pytest.mark.asyncio
    async def test_delete_team_cascades_memberships(self) -> None:
        team = await TeamService.create_team(name="eng", display_name="Eng")
        await TeamService.add_member(team.id, user_id="u1", user_email="u@co.com", user_name="U")
        await TeamService.set_api_key(
            team.id, provider="openai", api_key="sk-test", created_by="u@co.com"
        )
        await TeamService.delete_team(team.id)

        # Memberships and keys should be gone
        members = await TeamService.get_team_members(team.id)
        assert len(members) == 0
        keys = await TeamService.list_api_keys(team.id)
        assert len(keys) == 0

    @pytest.mark.asyncio
    async def test_seed_default_team(self) -> None:
        team = await TeamService.seed_default_team()
        assert team is not None
        assert team.name == "default"

        # Should not create another one
        team2 = await TeamService.seed_default_team()
        assert team2 is None

    @pytest.mark.asyncio
    async def test_get_team_by_name(self) -> None:
        await TeamService.create_team(name="eng", display_name="Engineering")
        team = await TeamService.get_team_by_name("eng")
        assert team is not None
        assert team.display_name == "Engineering"

        missing = await TeamService.get_team_by_name("nonexistent")
        assert missing is None
