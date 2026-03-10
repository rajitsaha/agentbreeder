"""Authentication routes — login, register, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from api.models.database import User
from api.models.schemas import (
    ApiResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from api.services.auth import authenticate_user, create_access_token, create_user, get_user_by_email

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    """Authenticate and return a JWT token."""
    user = await authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(str(user.id), user.email, user.role.value)
    return ApiResponse(data=TokenResponse(access_token=token))


@router.post("/register", response_model=ApiResponse[UserResponse], status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserResponse]:
    """Create a new user account."""
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )
    user = await create_user(db, body.email, body.name, body.password, body.team)
    return ApiResponse(data=UserResponse.model_validate(user))


@router.get("/me", response_model=ApiResponse[UserResponse])
async def me(
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserResponse]:
    """Return the currently authenticated user."""
    return ApiResponse(data=UserResponse.model_validate(current_user))
