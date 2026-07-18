import secrets
import string

import structlog
from fastapi import APIRouter, Header, Request, Response, status

from app.api.v1.deps import DB, CurrentUser, Redis
from app.core.config import get_settings
from app.schemas.auth import LinkCodeResponse
from app.services import telegram_bot_service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])

LINK_CODE_TTL = 900  # 15 minutes
LINK_CODE_PREFIX = "telegram_link:"


@router.post("/webhook")
async def webhook(
    request: Request,
    db: DB,
    redis: Redis,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    settings = get_settings()
    # SEC-004: empty body on invalid secret — no information leaked to potential attackers
    if not x_telegram_bot_api_secret_token or not secrets.compare_digest(
        x_telegram_bot_api_secret_token, settings.telegram_webhook_secret
    ):
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    try:
        update = await request.json()
    except Exception:
        return Response(content='{"ok":"true"}', media_type="application/json")

    try:
        await telegram_bot_service.handle_update(update=update, db=db, redis=redis)
    except Exception:
        log.exception("telegram_webhook_handler_error")

    return Response(content='{"ok":"true"}', media_type="application/json")


@router.post("/link-code", response_model=LinkCodeResponse)
async def generate_link_code(
    current_user: CurrentUser,
    redis: Redis,
) -> LinkCodeResponse:
    settings = get_settings()
    alphabet = string.ascii_lowercase + string.digits
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    await redis.setex(f"{LINK_CODE_PREFIX}{code}", LINK_CODE_TTL, str(current_user.id))
    deep_link = f"https://t.me/{settings.telegram_bot_name}?start={code}"
    return LinkCodeResponse(code=code, expires_in_seconds=LINK_CODE_TTL, deep_link=deep_link)


@router.delete("/link", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_telegram(
    current_user: CurrentUser,
    db: DB,
) -> None:
    current_user.telegram_chat_id = None
    current_user.telegram_linked_at = None
    await db.commit()
