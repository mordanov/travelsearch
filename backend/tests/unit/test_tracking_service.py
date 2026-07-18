"""Unit tests for TrackingService."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tracking_service import (
    InvalidIntervalError,
    TrackingLimitExceededError,
    TrackingNotFoundError,
    create_tracked_search,
    remove_tracked_search,
)


def _make_user(telegram_chat_id: int | None = None) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.telegram_chat_id = telegram_chat_id
    return user


def _make_search(user_id: uuid.UUID) -> MagicMock:
    search = MagicMock()
    search.id = uuid.uuid4()
    search.user_id = user_id
    return search


def _make_tracked_search() -> MagicMock:
    ts = MagicMock()
    ts.id = uuid.uuid4()
    ts.interval_hours = 24
    ts.next_run_at = datetime.utcnow()
    return ts


class TestCreateTrackedSearch:
    @pytest.mark.asyncio
    async def test_creates_new_tracked_search(self) -> None:
        user = _make_user()
        search = _make_search(user.id)
        db = AsyncMock()

        with (
            patch("app.services.tracking_service.get_search", AsyncMock(return_value=search)),
            patch(
                "app.services.tracking_service.tracking_repository.get_tracked_search_by_search_id",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.tracking_service.tracking_repository.count_active_tracked_searches",
                AsyncMock(return_value=0),
            ),
            patch(
                "app.services.tracking_service.tracking_repository.create_tracked_search",
                AsyncMock(return_value=_make_tracked_search()),
            ),
        ):
            ts, warning = await create_tracked_search(db, user, search.id, 24)
            assert ts is not None
            assert warning is not None  # no telegram_chat_id → warning

    @pytest.mark.asyncio
    async def test_returns_existing_on_duplicate(self) -> None:
        user = _make_user(telegram_chat_id=12345)
        search = _make_search(user.id)
        existing = _make_tracked_search()
        db = AsyncMock()

        with (
            patch("app.services.tracking_service.get_search", AsyncMock(return_value=search)),
            patch(
                "app.services.tracking_service.tracking_repository.get_tracked_search_by_search_id",
                AsyncMock(return_value=existing),
            ),
        ):
            ts, warning = await create_tracked_search(db, user, search.id, 12)
            assert ts is existing
            assert ts.interval_hours == 12
            assert warning is None

    @pytest.mark.asyncio
    async def test_raises_on_limit_exceeded(self) -> None:
        user = _make_user()
        search = _make_search(user.id)
        db = AsyncMock()

        with (
            patch("app.services.tracking_service.get_search", AsyncMock(return_value=search)),
            patch(
                "app.services.tracking_service.tracking_repository.get_tracked_search_by_search_id",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.tracking_service.tracking_repository.count_active_tracked_searches",
                AsyncMock(return_value=10),
            ),
        ):
            with pytest.raises(TrackingLimitExceededError):
                await create_tracked_search(db, user, search.id, 24)

    @pytest.mark.asyncio
    async def test_raises_on_invalid_interval(self) -> None:
        user = _make_user()
        db = AsyncMock()
        with pytest.raises(InvalidIntervalError):
            await create_tracked_search(db, user, uuid.uuid4(), 7)

    @pytest.mark.asyncio
    async def test_raises_on_search_not_found(self) -> None:
        user = _make_user()
        db = AsyncMock()
        with (
            patch("app.services.tracking_service.get_search", AsyncMock(return_value=None)),
        ):
            with pytest.raises(TrackingNotFoundError):
                await create_tracked_search(db, user, uuid.uuid4(), 24)


class TestRemoveTrackedSearch:
    @pytest.mark.asyncio
    async def test_deactivates_on_remove(self) -> None:
        user_id = uuid.uuid4()
        ts = _make_tracked_search()
        db = AsyncMock()

        with (
            patch(
                "app.services.tracking_service.tracking_repository.get_tracked_search_by_id",
                AsyncMock(return_value=ts),
            ),
            patch(
                "app.services.tracking_service.tracking_repository.deactivate_tracked_search",
                AsyncMock(),
            ) as mock_deactivate,
        ):
            await remove_tracked_search(db, user_id, ts.id)
            mock_deactivate.assert_called_once_with(db, ts)

    @pytest.mark.asyncio
    async def test_raises_not_found(self) -> None:
        db = AsyncMock()
        with (
            patch(
                "app.services.tracking_service.tracking_repository.get_tracked_search_by_id",
                AsyncMock(return_value=None),
            ),
        ):
            with pytest.raises(TrackingNotFoundError):
                await remove_tracked_search(db, uuid.uuid4(), uuid.uuid4())
