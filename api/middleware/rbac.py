"""RBAC middleware — FastAPI dependencies for role-based access control."""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from api.auth import get_current_user
from api.models.database import User
from api.services.team_service import TeamService

logger = logging.getLogger(__name__)


def require_role(min_role: str, resource_team: str | None = None) -> Callable:
    """FastAPI dependency — checks current user has at least min_role on the resource's team.

    Usage:
        @router.post("/teams", dependencies=[Depends(require_role("admin"))])
        async def create_team(...): ...

    Or with a specific team:
        @router.put("/teams/{team_id}",
            dependencies=[Depends(require_role("admin", resource_team="team-id"))])
    """

    async def check(user: User = Depends(get_current_user)) -> User:
        from api.services.team_service import ROLE_HIERARCHY

        if min_role not in ROLE_HIERARCHY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid role requirement: {min_role}",
            )

        required_level = ROLE_HIERARCHY[min_role]
        user_id = str(user.id)

        if resource_team:
            # Check specific team
            user_role = await TeamService.get_user_role_in_team(user_id, resource_team)
            if user_role is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not a member of this team",
                )
            user_level = ROLE_HIERARCHY.get(user_role, 0)
            if user_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires {min_role} role, you have {user_role}",
                )
        else:
            # Check if user has sufficient role in ANY team using DB-backed query
            user_teams = await TeamService.get_user_teams(user_id)
            max_level = 0
            for team in user_teams:
                role = await TeamService.get_user_role_in_team(user_id, team.id)
                if role is not None:
                    level = ROLE_HIERARCHY.get(role, 0)
                    if level > max_level:
                        max_level = level

            # Platform admins always pass
            if hasattr(user, "role") and str(user.role) == "admin":
                max_level = max(max_level, ROLE_HIERARCHY.get("admin", 3))

            if max_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires {min_role} role",
                )

        return user

    return check


async def get_user_team_role(
    team_id: str,
    user: User = Depends(get_current_user),
) -> str:
    """FastAPI dependency — returns the user's role in the given team.

    Raises 403 if user is not a member of the team.
    """
    user_id = str(user.id)
    role = await TeamService.get_user_role_in_team(user_id, team_id)
    if role is None:
        # Allow platform admins (from the user model) to access any team
        if hasattr(user, "role") and str(user.role) == "admin":
            return "admin"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this team",
        )
    return role
