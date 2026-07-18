import redis.asyncio as aioredis
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.repositories import user_repository

log = structlog.get_logger(__name__)

REVOKED_RT_PREFIX = "revoked_rt:"


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await user_repository.get_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def create_tokens(user: User) -> dict[str, str]:
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


async def refresh_access_token(
    refresh_token: str,
    redis: aioredis.Redis,
) -> dict[str, str] | None:
    """Rotate refresh token: validate old token, revoke it, issue new access+refresh pair."""
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        return None

    if payload.get("type") != "refresh":
        return None

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if user_id is None or jti is None:
        return None

    # Check revocation list using the per-token jti (SEC-001, SEC-006)
    revoked = await redis.get(f"{REVOKED_RT_PREFIX}{jti}")
    if revoked:
        return None

    # Revoke the old token before issuing the new one (rotation per SEC-001)
    ttl = int(payload["exp"]) - int(payload["iat"])
    await redis.setex(f"{REVOKED_RT_PREFIX}{jti}", max(ttl, 1), "1")

    new_access = create_access_token(str(user_id))
    new_refresh = create_refresh_token(str(user_id))
    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


async def revoke_refresh_token(
    refresh_token: str,
    redis: aioredis.Redis,
) -> None:
    """Revoke a refresh token by its jti. Used on logout."""
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        return

    jti = payload.get("jti")
    if jti is None:
        return

    from app.core.config import get_settings

    settings = get_settings()
    ttl = settings.refresh_token_expire_days * 86400
    await redis.setex(f"{REVOKED_RT_PREFIX}{jti}", ttl, "1")
