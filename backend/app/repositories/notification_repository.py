import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_log import NotificationLog, PriceSnapshot


async def create_notification_log(
    db: AsyncSession,
    user_id: uuid.UUID,
    notification_type: str,
    property_id: uuid.UUID,
    property_url: str,
    price_after: float,
    price_before: float | None = None,
    tracked_search_id: uuid.UUID | None = None,
    tracked_property_id: uuid.UUID | None = None,
    delivery_status: str = "sent",
    channel: str = "telegram",
) -> NotificationLog:
    log = NotificationLog(
        user_id=user_id,
        type=notification_type,
        channel=channel,
        property_id=property_id,
        tracked_search_id=tracked_search_id,
        tracked_property_id=tracked_property_id,
        price_before=price_before,
        price_after=price_after,
        property_url=property_url,
        delivery_status=delivery_status,
    )
    db.add(log)
    await db.flush()
    return log


async def get_notifications_page(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    size: int = 50,
    notification_type: str | None = None,
) -> tuple[list[tuple[NotificationLog, str]], int]:
    from app.models.property import Property

    stmt = (
        select(NotificationLog, Property.name)
        .join(Property, Property.id == NotificationLog.property_id)
        .where(NotificationLog.user_id == user_id)
    )
    if notification_type is not None:
        stmt = stmt.where(NotificationLog.type == notification_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(NotificationLog.sent_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    rows = result.fetchall()
    return [(r[0], r[1]) for r in rows], total


async def create_price_snapshot(
    db: AsyncSession,
    property_id: uuid.UUID,
    user_id: uuid.UUID,
    check_in: datetime,
    check_out: datetime,
    price: float,
    source: str,
) -> PriceSnapshot:
    snap = PriceSnapshot(
        property_id=property_id,
        user_id=user_id,
        check_in=check_in,
        check_out=check_out,
        price=price,
        source=source,
    )
    db.add(snap)
    await db.flush()
    return snap
