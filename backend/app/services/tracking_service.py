import uuid
from datetime import datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracked_property import TrackedProperty
from app.models.tracked_search import TrackedSearch
from app.models.user import User
from app.repositories import tracking_repository
from app.repositories.property_repository import get_by_id as get_property_by_id
from app.repositories.search_repository import get_search

log = structlog.get_logger(__name__)

VALID_INTERVALS = {6, 12, 24, 48}
MAX_TRACKED_SEARCHES = 10
MAX_TRACKED_PROPERTIES = 20


class TrackingLimitExceededError(Exception):
    pass


class InvalidIntervalError(Exception):
    pass


class TrackingNotFoundError(Exception):
    pass


def _validate_interval(interval_hours: int) -> None:
    if interval_hours not in VALID_INTERVALS:
        raise InvalidIntervalError(
            f"interval_hours must be one of {sorted(VALID_INTERVALS)}, got {interval_hours}"
        )


def _telegram_warning(user: User) -> str | None:
    if not user.telegram_chat_id:
        return (
            "Telegram is not linked. Notifications will be recorded in-app but not sent "
            "until you link your Telegram account."
        )
    return None


async def create_tracked_search(
    db: AsyncSession,
    user: User,
    search_id: uuid.UUID,
    interval_hours: int,
) -> tuple[TrackedSearch, str | None]:
    _validate_interval(interval_hours)

    search = await get_search(db, search_id)
    if search is None or search.user_id != user.id:
        raise TrackingNotFoundError("Search not found")

    existing = await tracking_repository.get_tracked_search_by_search_id(
        db, user.id, search_id
    )
    if existing is not None:
        existing.interval_hours = interval_hours
        existing.next_run_at = datetime.utcnow() + timedelta(hours=interval_hours)
        await db.flush()
        return existing, _telegram_warning(user)

    count = await tracking_repository.count_active_tracked_searches(db, user.id)
    if count >= MAX_TRACKED_SEARCHES:
        raise TrackingLimitExceededError(
            f"Maximum {MAX_TRACKED_SEARCHES} active tracked searches allowed"
        )

    ts = await tracking_repository.create_tracked_search(
        db=db,
        user_id=user.id,
        search_id=search_id,
        interval_hours=interval_hours,
        next_run_at=datetime.utcnow() + timedelta(hours=interval_hours),
    )
    return ts, _telegram_warning(user)


async def remove_tracked_search(
    db: AsyncSession, user_id: uuid.UUID, tracked_search_id: uuid.UUID
) -> None:
    ts = await tracking_repository.get_tracked_search_by_id(db, tracked_search_id, user_id)
    if ts is None:
        raise TrackingNotFoundError("Tracked search not found")
    await tracking_repository.deactivate_tracked_search(db, ts)


async def create_tracked_property(
    db: AsyncSession,
    user: User,
    property_id: uuid.UUID,
    check_in: datetime,
    check_out: datetime,
    interval_hours: int,
) -> tuple[TrackedProperty, str | None]:
    _validate_interval(interval_hours)

    prop = await get_property_by_id(db, property_id)
    if prop is None:
        raise TrackingNotFoundError("Property not found")

    existing = await tracking_repository.get_tracked_property_duplicate(
        db, user.id, property_id, check_in, check_out
    )
    if existing is not None:
        existing.interval_hours = interval_hours
        existing.next_run_at = datetime.utcnow() + timedelta(hours=interval_hours)
        await db.flush()
        return existing, _telegram_warning(user)

    count = await tracking_repository.count_active_tracked_properties(db, user.id)
    if count >= MAX_TRACKED_PROPERTIES:
        raise TrackingLimitExceededError(
            f"Maximum {MAX_TRACKED_PROPERTIES} active tracked properties allowed"
        )

    tp = await tracking_repository.create_tracked_property(
        db=db,
        user_id=user.id,
        property_id=property_id,
        check_in=check_in,
        check_out=check_out,
        interval_hours=interval_hours,
        next_run_at=datetime.utcnow() + timedelta(hours=interval_hours),
    )
    return tp, _telegram_warning(user)


async def remove_tracked_property(
    db: AsyncSession, user_id: uuid.UUID, tracked_property_id: uuid.UUID
) -> None:
    tp = await tracking_repository.get_tracked_property_by_id(
        db, tracked_property_id, user_id
    )
    if tp is None:
        raise TrackingNotFoundError("Tracked property not found")
    await tracking_repository.deactivate_tracked_property(db, tp)
