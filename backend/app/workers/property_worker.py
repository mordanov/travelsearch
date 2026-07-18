"""
arq job: re-check TrackedProperty for price drops.
Safe-discard invariant: never write to DB if scrape status != OK.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.models.tracked_property import TrackedProperty
from app.notifiers.base import NotificationMessage, NotificationType
from app.notifiers.telegram import TelegramNotifier
from app.providers.base import ScrapeStatus
from app.repositories import notification_repository, tracking_repository
from app.repositories.property_repository import get_by_id as get_property

log = structlog.get_logger(__name__)


async def recheck_tracked_property(ctx: dict[str, Any]) -> None:
    # Constitution I: providers injected via arq ctx (populated by scheduler.on_startup)
    provider_map: dict[str, Any] = ctx.get("providers", {})
    factory = get_session_factory()
    async with factory() as db:
        overdue = await tracking_repository.get_overdue_tracked_properties(db)
        log.info("property_worker_tick", overdue_count=len(overdue))

        notifier = TelegramNotifier()

        for tp in overdue:
            await _process_tracked_property(db, tp, notifier, provider_map)

        await db.commit()


async def _process_tracked_property(
    db: AsyncSession,
    tp: TrackedProperty,
    notifier: TelegramNotifier,
    provider_map: dict[str, Any],
) -> None:
    from app.repositories.user_repository import get_by_id as get_user

    # Auto-deactivate if check-in has passed
    today = datetime.utcnow().date()
    check_in_date = tp.check_in.date() if hasattr(tp.check_in, "date") else tp.check_in
    if check_in_date <= today:
        tp.is_active = False
        await db.flush()
        log.info("tracked_property_auto_deactivated", tp_id=tp.id)
        return

    prop = await get_property(db, tp.property_id)
    if prop is None:
        log.warning("tracked_property_missing_property", tp_id=tp.id)
        return

    user = await get_user(db, tp.user_id)
    if user is None:
        return

    prov = provider_map.get(prop.provider)
    if prov is None:
        log.warning("tracked_property_no_provider", provider=prop.provider)
        return

    check_in = tp.check_in.date() if hasattr(tp.check_in, "date") else tp.check_in
    check_out = tp.check_out.date() if hasattr(tp.check_out, "date") else tp.check_out

    try:
        detail = await prov.details(
            provider_property_id=prop.provider_property_id,
            check_in=check_in,
            check_out=check_out,
            guests=1,  # TrackedProperty has no guests column — MVP simplification
        )
    except Exception:
        log.exception("property_worker_provider_error", tp_id=tp.id)
        return

    if detail.status != ScrapeStatus.OK or detail.listing is None:
        log.warning(
            "property_worker_cycle_discarded",
            tp_id=tp.id,
            status=detail.status,
        )
        return

    current_price = Decimal(str(detail.listing.total_price))
    min_price = Decimal(str(tp.min_price_seen)) if tp.min_price_seen is not None else None

    if min_price is not None and current_price < min_price:
        notification_row = await notification_repository.create_notification_log(
            db=db,
            user_id=tp.user_id,
            notification_type="price_drop",
            property_id=prop.id,
            property_url=prop.url,
            price_after=float(current_price),
            price_before=float(min_price),
            tracked_property_id=tp.id,
            delivery_status="pending",
        )

        await notification_repository.create_price_snapshot(
            db=db,
            property_id=prop.id,
            user_id=tp.user_id,
            check_in=tp.check_in,
            check_out=tp.check_out,
            price=float(current_price),
            source="property_worker",
        )

        if user.telegram_chat_id:
            msg = NotificationMessage(
                type=NotificationType.PRICE_DROP,
                property_name=prop.name,
                property_url=prop.url,
                price_after=current_price,
                price_before=min_price,
            )
            ok = await notifier.send(user.telegram_chat_id, msg)
            notification_row.delivery_status = "sent" if ok else "failed"

    now = datetime.utcnow()
    next_run_at = now + timedelta(hours=tp.interval_hours)
    await tracking_repository.update_tracked_property_after_run(
        db, tp, float(current_price), next_run_at
    )
    await db.commit()
    log.info("property_worker_cycle_complete", tp_id=tp.id)
