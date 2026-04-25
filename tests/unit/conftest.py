"""Shared test fixtures for unit tests.

Provides a default authenticated viewer user for all API tests so that
pre-existing tests continue to work after Phase 1 RBAC enforcement.

Tests that explicitly test 401/403 behavior (like test_rbac_phase1.py)
call endpoints without the Authorization header — HTTPBearer returns None
credentials before get_current_user is invoked, so those tests are NOT
affected by the patches here.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models.enums import UserRole
from api.services.auth import create_access_token, hash_password


def _make_default_admin():
    """Return a mock User ORM object with admin role (passes all RBAC checks)."""
    uid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user = MagicMock()
    user.id = uid
    user.email = "default-admin@test.com"
    user.name = "Default Admin"
    user.role = UserRole.admin
    user.team = "engineering"
    user.is_active = True
    user.password_hash = hash_password("testpass")
    return user


_DEFAULT_ADMIN = _make_default_admin()
_DEFAULT_ADMIN_ID = str(_DEFAULT_ADMIN.id)
_DEFAULT_TOKEN = create_access_token(_DEFAULT_ADMIN_ID, "default-admin@test.com", "admin")


@pytest.fixture(autouse=True)
def _auto_auth(request):
    """Auto-patch JWT auth to return a default viewer for all API tests.

    This fixture is skipped for test modules that explicitly test
    authentication behavior (they manage their own auth mocking), and for
    tests marked with @pytest.mark.no_auto_auth.
    """
    # Skip auto-auth for tests that explicitly test 401/403 behavior
    skip_modules = {"test_rbac_phase1", "test_auth", "test_team_service"}
    module_name = request.module.__name__.split(".")[-1]
    if module_name in skip_modules:
        yield
        return

    # Allow individual tests to opt out of auto-auth (e.g. to test 401 behavior)
    if request.node.get_closest_marker("no_auto_auth"):
        yield
        return

    async def _mock_get_current_user():
        return _DEFAULT_ADMIN

    # Override the FastAPI dependency at the app level so that all routes
    # using Depends(get_current_user) receive the default admin without needing
    # a real JWT. require_role() inner checks call get_current_user internally
    # via Depends, so this override propagates through role checks too.
    # Platform admins bypass the team membership check in require_role, so
    # using admin role here means all existing tests pass without change.
    from api.auth import get_current_user, get_optional_user
    from api.main import app

    async def _mock_get_optional_user():
        return _DEFAULT_ADMIN

    app.dependency_overrides[get_current_user] = _mock_get_current_user
    app.dependency_overrides[get_optional_user] = _mock_get_optional_user

    # Also patch TeamService.get_user_teams to return empty (admin bypass applies)
    with patch(
        "api.services.team_service.TeamService.get_user_teams",
        new_callable=AsyncMock,
        return_value=[],
    ):
        yield

    # Clean up overrides after each test
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)
