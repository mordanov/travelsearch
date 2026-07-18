"""Unit tests for property worker logic."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.base import PropertyDetail, PropertyListing, ScrapeStatus


def _make_prop() -> MagicMock:
    prop = MagicMock()
    prop.id = uuid.uuid4()
    prop.provider = "booking"
    prop.provider_property_id = "hotel123"
    prop.name = "Test Hotel"
    prop.url = "https://booking.com/hotel123"
    return prop


def _make_user(telegram_chat_id: int | None = None) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.telegram_chat_id = telegram_chat_id
    return user


def _make_tracked_property(min_price: float | None, check_in: date | None = None) -> MagicMock:
    tp = MagicMock()
    tp.id = uuid.uuid4()
    tp.user_id = uuid.uuid4()
    tp.property_id = uuid.uuid4()
    tp.interval_hours = 24
    tp.min_price_seen = min_price
    ci = check_in or date(2027, 1, 1)
    tp.check_in = datetime.combine(ci, datetime.min.time())
    tp.check_out = datetime.combine(date(2027, 1, 8), datetime.min.time())
    tp.is_active = True
    return tp


class TestPropertyWorkerLogic:

    @pytest.mark.asyncio
    async def test_price_drop_creates_notification(self) -> None:
        from app.workers.property_worker import _process_tracked_property

        prop = _make_prop()
        user = _make_user(telegram_chat_id=12345)
        tp = _make_tracked_property(min_price=200.0)

        listing = PropertyListing(
            provider="booking",
            provider_property_id="hotel123",
            name="Test Hotel",
            url="https://booking.com/hotel123",
            price_per_night=Decimal("20"),
            total_price=Decimal("140"),  # lower than 200
        )
        detail = PropertyDetail(status=ScrapeStatus.OK, listing=listing, provider="booking")

        mock_prov = AsyncMock()
        mock_prov.details = AsyncMock(return_value=detail)
        provider_map = {"booking": mock_prov}

        notifier = AsyncMock()
        notifier.send = AsyncMock(return_value=True)

        create_notif = AsyncMock(return_value=MagicMock())
        create_snap = AsyncMock(return_value=MagicMock())

        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        with (
            patch("app.workers.property_worker.get_property", AsyncMock(return_value=prop)),
            patch(
                "app.repositories.user_repository.get_by_id",
                AsyncMock(return_value=user),
            ),
            patch(
                "app.workers.property_worker.notification_repository.create_notification_log",
                create_notif,
            ),
            patch(
                "app.workers.property_worker.notification_repository.create_price_snapshot",
                create_snap,
            ),
            patch(
                "app.workers.property_worker.tracking_repository.update_tracked_property_after_run",
                AsyncMock(),
            ),
        ):
            await _process_tracked_property(db, tp, notifier, provider_map)

        create_notif.assert_called_once()
        call_kwargs = create_notif.call_args.kwargs
        assert call_kwargs["notification_type"] == "price_drop"
        notifier.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_price_above_min_no_notification(self) -> None:
        from app.workers.property_worker import _process_tracked_property

        prop = _make_prop()
        user = _make_user(telegram_chat_id=12345)
        tp = _make_tracked_property(min_price=100.0)  # current > min → no notification

        listing = PropertyListing(
            provider="booking",
            provider_property_id="hotel123",
            name="Test Hotel",
            url="https://booking.com/hotel123",
            price_per_night=Decimal("30"),
            total_price=Decimal("210"),  # higher than 100
        )
        detail = PropertyDetail(status=ScrapeStatus.OK, listing=listing, provider="booking")

        mock_prov = AsyncMock()
        mock_prov.details = AsyncMock(return_value=detail)
        provider_map = {"booking": mock_prov}
        notifier = AsyncMock()
        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        with (
            patch("app.workers.property_worker.get_property", AsyncMock(return_value=prop)),
            patch("app.repositories.user_repository.get_by_id", AsyncMock(return_value=user)),
            patch(
                "app.workers.property_worker.notification_repository.create_notification_log",
                AsyncMock(),
            ) as create_notif,
            patch(
                "app.workers.property_worker.tracking_repository.update_tracked_property_after_run",
                AsyncMock(),
            ),
        ):
            await _process_tracked_property(db, tp, notifier, provider_map)

        create_notif.assert_not_called()
        notifier.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocked_status_discards(self) -> None:
        from app.workers.property_worker import _process_tracked_property

        prop = _make_prop()
        user = _make_user()
        tp = _make_tracked_property(min_price=100.0)

        detail = PropertyDetail(status=ScrapeStatus.BLOCKED, listing=None, provider="booking")
        mock_prov = AsyncMock()
        mock_prov.details = AsyncMock(return_value=detail)
        provider_map = {"booking": mock_prov}
        notifier = AsyncMock()
        db = AsyncMock()

        with (
            patch("app.workers.property_worker.get_property", AsyncMock(return_value=prop)),
            patch("app.repositories.user_repository.get_by_id", AsyncMock(return_value=user)),
            patch(
                "app.workers.property_worker.notification_repository.create_notification_log",
                AsyncMock(),
            ) as create_notif,
        ):
            await _process_tracked_property(db, tp, notifier, provider_map)

        create_notif.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_in_passed_deactivates(self) -> None:
        from app.workers.property_worker import _process_tracked_property

        prop = _make_prop()
        user = _make_user()
        # check_in in the past
        past_checkin = date(2020, 1, 1)
        tp = _make_tracked_property(min_price=100.0, check_in=past_checkin)

        notifier = AsyncMock()
        db = AsyncMock()
        db.flush = AsyncMock()

        with (
            patch("app.workers.property_worker.get_property", AsyncMock(return_value=prop)),
            patch("app.repositories.user_repository.get_by_id", AsyncMock(return_value=user)),
        ):
            await _process_tracked_property(db, tp, notifier, {})

        assert tp.is_active is False
