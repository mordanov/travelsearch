import uuid
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import tracking_repository, user_repository
from app.services.tracking_service import (
    TrackingLimitExceededError,
    TrackingNotFoundError,
    create_tracked_property,
    remove_tracked_property,
)

log = structlog.get_logger(__name__)

LINK_CODE_PREFIX = "telegram_link:"


async def _send_reply(chat_id: int, text: str) -> None:
    """Send a reply via Telegram Bot API. Deferred to notifier interface in production."""
    import httpx

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.telegram_bot_token:
        log.warning("telegram_bot_token_not_set")
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception:
        log.exception("telegram_send_reply_error", chat_id=chat_id)


async def handle_update(
    update: dict[str, Any],
    db: AsyncSession,
    redis: aioredis.Redis,  # type: ignore[type-arg]
) -> None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id: int = message["chat"]["id"]
    text: str = message.get("text", "").strip()

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ""
        await _handle_start(chat_id=chat_id, code=code, db=db, redis=redis)
    elif text.startswith("/follow"):
        parts = text.split(maxsplit=1)
        url = parts[1].strip() if len(parts) > 1 else ""
        await _handle_follow(chat_id=chat_id, url=url, db=db)
    elif text.startswith("/unfollow"):
        parts = text.split(maxsplit=1)
        url = parts[1].strip() if len(parts) > 1 else ""
        await _handle_unfollow(chat_id=chat_id, url=url, db=db)
    elif text.startswith("/list"):
        await _handle_list(chat_id=chat_id, db=db)
    else:
        await _send_reply(chat_id, "Unknown command. Try /follow <url>, /unfollow <url>, /list")


async def _handle_start(
    chat_id: int,
    code: str,
    db: AsyncSession,
    redis: aioredis.Redis,  # type: ignore[type-arg]
) -> None:
    if not code:
        await _send_reply(chat_id, "Welcome! Use the app to generate a link code.")
        return

    user_id_str = await redis.get(f"{LINK_CODE_PREFIX}{code}")
    if not user_id_str:
        await _send_reply(chat_id, "Link code expired or already used. Please generate a new one.")
        return

    await redis.delete(f"{LINK_CODE_PREFIX}{code}")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        log.error("invalid_user_id_in_link_code", code=code)
        await _send_reply(chat_id, "Invalid link code.")
        return

    user = await user_repository.get_by_id(db, user_id)
    if user is None:
        await _send_reply(chat_id, "Account not found.")
        return

    user.telegram_chat_id = chat_id
    user.telegram_linked_at = datetime.utcnow()
    await db.commit()
    await _send_reply(chat_id, "Your Telegram account has been linked successfully!")


_ALLOWED_URL_HOSTS = (
    "booking.com",
    "www.booking.com",
    "airbnb.com",
    "www.airbnb.com",
    "airbnb.co.uk",
    "www.airbnb.co.uk",
)


def _is_allowed_url(url: str) -> bool:
    """SEC-003: allowlist check — only booking.com and airbnb.com domains accepted."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        # Require https and a recognised host
        if parsed.scheme not in ("https", "http"):
            return False
        host = parsed.netloc.lower().split(":")[0]  # strip port if present
        return any(
            host == allowed or host.endswith("." + allowed) for allowed in _ALLOWED_URL_HOSTS
        )
    except Exception:
        return False


async def _handle_follow(chat_id: int, url: str, db: AsyncSession) -> None:
    if not url:
        await _send_reply(chat_id, "Usage: /follow <booking or airbnb url with dates>")
        return

    # SEC-003: reject non-Booking/Airbnb URLs before any provider parsing
    if not _is_allowed_url(url):
        await _send_reply(chat_id, "Only Booking.com and Airbnb links are supported.")
        return

    user = await user_repository.get_by_telegram_chat_id(db, chat_id)
    if user is None:
        await _send_reply(chat_id, "Please link your account first using /start <code>.")
        return

    from app.providers.airbnb import AirbnbProvider
    from app.providers.booking import BookingProvider

    providers = [BookingProvider(), AirbnbProvider()]
    parsed = None
    for prov in providers:
        parsed = prov.parse_url(url)
        if parsed is not None:
            break

    if parsed is None:
        await _send_reply(
            chat_id, "That URL is not a recognized Booking or Airbnb listing. Nothing created."
        )
        return

    if parsed.check_in is None or parsed.check_out is None:
        await _send_reply(
            chat_id,
            "Could not extract dates from the link. "
            "Please send a URL that includes check-in and check-out dates.",
        )
        return

    # Find or create property by provider identity
    from sqlalchemy import select

    from app.models.property import Property

    result = await db.execute(
        select(Property).where(
            Property.provider == parsed.provider,
            Property.provider_property_id == parsed.provider_property_id,
        )
    )
    prop = result.scalar_one_or_none()
    if prop is None:
        await _send_reply(
            chat_id,
            "Property not found in our database yet. Search for it first to add it.",
        )
        return

    check_in_dt = datetime.combine(parsed.check_in, datetime.min.time())
    check_out_dt = datetime.combine(parsed.check_out, datetime.min.time())

    try:
        tp, _ = await create_tracked_property(
            db=db,
            user=user,
            property_id=prop.id,
            check_in=check_in_dt,
            check_out=check_out_dt,
            interval_hours=24,
        )
        await db.commit()
        await _send_reply(
            chat_id,
            f"Tracking started for <b>{prop.name}</b> "
            f"({parsed.check_in} → {parsed.check_out}). "
            f"I'll notify you if the price drops!",
        )
    except TrackingLimitExceededError as exc:
        await _send_reply(chat_id, f"Limit reached: {exc}")
    except TrackingNotFoundError as exc:
        await _send_reply(chat_id, str(exc))


async def _handle_unfollow(chat_id: int, url: str, db: AsyncSession) -> None:
    user = await user_repository.get_by_telegram_chat_id(db, chat_id)
    if user is None:
        await _send_reply(chat_id, "Please link your account first using /start <code>.")
        return

    if not url:
        await _send_reply(chat_id, "Usage: /unfollow <url>")
        return

    # SEC-003: reject non-Booking/Airbnb URLs before any provider parsing
    if not _is_allowed_url(url):
        await _send_reply(chat_id, "Only Booking.com and Airbnb links are supported.")
        return

    from app.providers.airbnb import AirbnbProvider
    from app.providers.booking import BookingProvider

    providers = [BookingProvider(), AirbnbProvider()]
    parsed = None
    for prov in providers:
        parsed = prov.parse_url(url)
        if parsed is not None:
            break

    if parsed is None:
        await _send_reply(chat_id, "URL not recognized.")
        return

    from sqlalchemy import select

    from app.models.property import Property
    from app.models.tracked_property import TrackedProperty

    result = await db.execute(
        select(Property).where(
            Property.provider == parsed.provider,
            Property.provider_property_id == parsed.provider_property_id,
        )
    )
    prop = result.scalar_one_or_none()
    if prop is None:
        await _send_reply(chat_id, "Property not tracked.")
        return

    if parsed.check_in and parsed.check_out:
        check_in_dt = datetime.combine(parsed.check_in, datetime.min.time())
        check_out_dt = datetime.combine(parsed.check_out, datetime.min.time())
        result2 = await db.execute(
            select(TrackedProperty).where(
                TrackedProperty.user_id == user.id,
                TrackedProperty.property_id == prop.id,
                TrackedProperty.check_in == check_in_dt,
                TrackedProperty.check_out == check_out_dt,
                TrackedProperty.is_active == True,  # noqa: E712
            )
        )
        tp = result2.scalar_one_or_none()
        if tp is None:
            await _send_reply(chat_id, "Property not tracked for those dates.")
            return
        try:
            await remove_tracked_property(db, user.id, tp.id)
            await db.commit()
            await _send_reply(chat_id, "Stopped tracking that property.")
        except TrackingNotFoundError:
            await _send_reply(chat_id, "Property not tracked.")
    else:
        await _send_reply(
            chat_id,
            "Could not extract dates from URL. Please include check-in and check-out dates.",
        )


async def _handle_list(chat_id: int, db: AsyncSession) -> None:
    user = await user_repository.get_by_telegram_chat_id(db, chat_id)
    if user is None:
        await _send_reply(chat_id, "Please link your account first using /start <code>.")
        return

    searches = await tracking_repository.get_active_tracked_searches(db, user.id)
    properties = await tracking_repository.get_active_tracked_properties(db, user.id)

    lines = ["<b>Your tracked items:</b>", ""]

    if searches:
        lines.append("<b>Tracked Searches:</b>")
        for ts in searches[:10]:
            from app.repositories.search_repository import get_search

            search = await get_search(db, ts.search_id)
            dest = search.destination if search else "?"
            lines.append(f"• {dest} (every {ts.interval_hours}h)")
    else:
        lines.append("No tracked searches.")

    lines.append("")

    if properties:
        lines.append("<b>Tracked Properties:</b>")
        from sqlalchemy import select

        from app.models.property import Property

        for tp in properties[:10]:
            result = await db.execute(select(Property).where(Property.id == tp.property_id))
            prop = result.scalar_one_or_none()
            name = prop.name if prop else "?"
            dates = f"{tp.check_in.date()} → {tp.check_out.date()}"
            lines.append(f"• {name} ({dates}, every {tp.interval_hours}h)")
    else:
        lines.append("No tracked properties.")

    await _send_reply(chat_id, "\n".join(lines))
