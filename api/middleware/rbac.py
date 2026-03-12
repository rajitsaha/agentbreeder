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
            # Check if user has sufficient role in ANY team
            max_level = 0
            memberships = [m for m in TeamService._memberships.values() if m.user_id == user_id]
            for m in memberships:
                level = ROLE_HIERARCHY.get(m.role, 0)
                if level > max_level:
                    max_level = level

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
