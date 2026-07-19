import uuid
from datetime import datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracked_property import TrackedProperty
from app.models.tracked_search import TrackedSearch, TrackedSearchSeenProperty

log = structlog.get_logger(__name__)


# --- TrackedSearch ---


async def create_tracked_search(
    db: AsyncSession,
    user_id: uuid.UUID,
    search_id: uuid.UUID,
    interval_hours: int,
    next_run_at: datetime,
) -> TrackedSearch:
    ts = TrackedSearch(
        user_id=user_id,
        search_id=search_id,
        interval_hours=interval_hours,
        next_run_at=next_run_at,
    )
    db.add(ts)
    await db.flush()
    return ts


async def get_tracked_search_by_search_id(
    db: AsyncSession, user_id: uuid.UUID, search_id: uuid.UUID
) -> TrackedSearch | None:
    result = await db.execute(
        select(TrackedSearch).where(
            TrackedSearch.user_id == user_id,
            TrackedSearch.search_id == search_id,
            TrackedSearch.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def count_active_tracked_searches(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(
            TrackedSearch.user_id == user_id,
            TrackedSearch.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one()


async def get_tracked_search_by_id(
    db: AsyncSession, tracked_search_id: uuid.UUID, user_id: uuid.UUID
) -> TrackedSearch | None:
    result = await db.execute(
        select(TrackedSearch).where(
            TrackedSearch.id == tracked_search_id,
            TrackedSearch.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def deactivate_tracked_search(db: AsyncSession, ts: TrackedSearch) -> None:
    ts.is_active = False
    await db.flush()


async def get_active_tracked_searches(db: AsyncSession, user_id: uuid.UUID) -> list[TrackedSearch]:
    result = await db.execute(
        select(TrackedSearch).where(
            TrackedSearch.user_id == user_id,
            TrackedSearch.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def get_overdue_tracked_searches(db: AsyncSession) -> list[TrackedSearch]:
    now = datetime.utcnow()
    result = await db.execute(
        select(TrackedSearch).where(
            TrackedSearch.is_active == True,  # noqa: E712
            TrackedSearch.next_run_at <= now,
        )
    )
    return list(result.scalars().all())


async def update_tracked_search_after_run(
    db: AsyncSession,
    ts: TrackedSearch,
    next_run_at: datetime,
) -> None:
    ts.last_successful_run_at = datetime.utcnow()
    ts.next_run_at = next_run_at
    await db.flush()


async def get_seen_properties(
    db: AsyncSession, tracked_search_id: uuid.UUID
) -> list[TrackedSearchSeenProperty]:
    result = await db.execute(
        select(TrackedSearchSeenProperty).where(
            TrackedSearchSeenProperty.tracked_search_id == tracked_search_id
        )
    )
    return list(result.scalars().all())


async def upsert_seen_property(
    db: AsyncSession,
    tracked_search_id: uuid.UUID,
    property_id: uuid.UUID,
    current_price: float,
    now: datetime,
) -> TrackedSearchSeenProperty:
    result = await db.execute(
        select(TrackedSearchSeenProperty).where(
            TrackedSearchSeenProperty.tracked_search_id == tracked_search_id,
            TrackedSearchSeenProperty.property_id == property_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        row = TrackedSearchSeenProperty(
            tracked_search_id=tracked_search_id,
            property_id=property_id,
            min_price_seen=current_price,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(row)
        await db.flush()
        return row
    if current_price < float(existing.min_price_seen):
        existing.min_price_seen = current_price
    existing.last_seen_at = now
    await db.flush()
    return existing


# --- TrackedProperty ---


async def create_tracked_property(
    db: AsyncSession,
    user_id: uuid.UUID,
    property_id: uuid.UUID,
    check_in: datetime,
    check_out: datetime,
    interval_hours: int,
    next_run_at: datetime,
) -> TrackedProperty:
    tp = TrackedProperty(
        user_id=user_id,
        property_id=property_id,
        check_in=check_in,
        check_out=check_out,
        interval_hours=interval_hours,
        next_run_at=next_run_at,
    )
    db.add(tp)
    await db.flush()
    return tp


async def get_tracked_property_duplicate(
    db: AsyncSession,
    user_id: uuid.UUID,
    property_id: uuid.UUID,
    check_in: datetime,
    check_out: datetime,
) -> TrackedProperty | None:
    result = await db.execute(
        select(TrackedProperty).where(
            TrackedProperty.user_id == user_id,
            TrackedProperty.property_id == property_id,
            TrackedProperty.check_in == check_in,
            TrackedProperty.check_out == check_out,
            TrackedProperty.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def count_active_tracked_properties(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(
            TrackedProperty.user_id == user_id,
            TrackedProperty.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one()


async def get_tracked_property_by_id(
    db: AsyncSession, tracked_property_id: uuid.UUID, user_id: uuid.UUID
) -> TrackedProperty | None:
    result = await db.execute(
        select(TrackedProperty).where(
            TrackedProperty.id == tracked_property_id,
            TrackedProperty.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def deactivate_tracked_property(db: AsyncSession, tp: TrackedProperty) -> None:
    tp.is_active = False
    await db.flush()


async def get_active_tracked_properties(
    db: AsyncSession, user_id: uuid.UUID
) -> list[TrackedProperty]:
    result = await db.execute(
        select(TrackedProperty).where(
            TrackedProperty.user_id == user_id,
            TrackedProperty.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def get_overdue_tracked_properties(db: AsyncSession) -> list[TrackedProperty]:
    now = datetime.utcnow()
    result = await db.execute(
        select(TrackedProperty).where(
            TrackedProperty.is_active == True,  # noqa: E712
            TrackedProperty.next_run_at <= now,
        )
    )
    return list(result.scalars().all())


async def update_tracked_property_after_run(
    db: AsyncSession,
    tp: TrackedProperty,
    current_price: float,
    next_run_at: datetime,
) -> None:
    if tp.min_price_seen is None or current_price < float(tp.min_price_seen):
        tp.min_price_seen = current_price
    tp.last_successful_run_at = datetime.utcnow()
    tp.next_run_at = next_run_at
    await db.flush()
