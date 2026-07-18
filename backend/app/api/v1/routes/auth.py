from typing import Annotated

import structlog
from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status

from app.api.v1.deps import DB, CurrentUser, Redis
from app.core.config import get_settings
from app.schemas.auth import LoginRequest, RefreshResponse, TokenResponse, UserResponse
from app.services import auth_service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
RATE_LIMIT_KEY = "login_attempts:{ip}"
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW = 600  # 10 minutes


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: DB,
    redis: Redis,
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"login_attempts:{client_ip}"
    attempts_raw = await redis.get(rate_key)
    attempts = int(attempts_raw) if attempts_raw else 0
    if attempts >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )

    user = await auth_service.authenticate_user(db, body.email, body.password)
    if user is None:
        await redis.incr(rate_key)
        await redis.expire(rate_key, RATE_LIMIT_WINDOW)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Reset rate-limit counter on successful login
    await redis.delete(rate_key)

    settings = get_settings()
    tokens = await auth_service.create_tokens(user)
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
    )
    return TokenResponse(access_token=tokens["access_token"])


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    response: Response,
    redis: Redis,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> RefreshResponse:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    # Returns new access+refresh pair (rotation) or None if invalid/revoked
    tokens = await auth_service.refresh_access_token(refresh_token, redis)
    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired or revoked",
        )
    # Set the rotated refresh token as the new HttpOnly cookie (SEC-001)
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
    )
    return RefreshResponse(access_token=tokens["access_token"])


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        telegram_is_linked=current_user.telegram_chat_id is not None,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    redis: Redis,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    if refresh_token:
        await auth_service.revoke_refresh_token(refresh_token, redis)
    response.delete_cookie(REFRESH_COOKIE)
