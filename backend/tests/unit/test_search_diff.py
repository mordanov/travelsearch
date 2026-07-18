"""Unit tests for search diff logic (compute_search_diff)."""
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from app.providers.base import PropertyListing
from app.workers.search_worker import NewListing, PriceDrop, compute_search_diff


def _make_listing(prop_id_str: str, total_price: float) -> PropertyListing:
    return PropertyListing(
        provider="booking",
        provider_property_id=prop_id_str,
        name=f"Hotel {prop_id_str}",
        url=f"https://booking.com/{prop_id_str}",
        price_per_night=Decimal(str(total_price / 7)),
        total_price=Decimal(str(total_price)),
    )


def _make_seen(min_price: float) -> MagicMock:
    sp = MagicMock()
    sp.min_price_seen = min_price
    return sp


class TestComputeSearchDiff:

    def test_empty_listings_safe_discard(self) -> None:
        events = compute_search_diff({}, {})
        assert events == []

    def test_new_listing_not_in_baseline(self) -> None:
        pid = str(uuid.uuid4())
        listings = {pid: _make_listing("prop1", 150.0)}
        events = compute_search_diff(listings, {})
        assert len(events) == 1
        assert isinstance(events[0], NewListing)
        assert events[0].prop_id == pid
        assert events[0].listing.provider_property_id == "prop1"

    def test_all_new_listings(self) -> None:
        pid1, pid2 = str(uuid.uuid4()), str(uuid.uuid4())
        listings = {
            pid1: _make_listing("prop1", 100.0),
            pid2: _make_listing("prop2", 200.0),
        }
        events = compute_search_diff(listings, {})
        assert len(events) == 2
        assert all(isinstance(e, NewListing) for e in events)

    def test_no_event_when_price_unchanged(self) -> None:
        pid = str(uuid.uuid4())
        listings = {pid: _make_listing("prop1", 100.0)}
        seen = {pid: _make_seen(100.0)}
        events = compute_search_diff(listings, seen)
        assert events == []

    def test_no_event_when_price_rises(self) -> None:
        pid = str(uuid.uuid4())
        listings = {pid: _make_listing("prop1", 120.0)}
        seen = {pid: _make_seen(100.0)}
        events = compute_search_diff(listings, seen)
        assert events == []

    def test_price_drop_detected(self) -> None:
        pid = str(uuid.uuid4())
        listings = {pid: _make_listing("prop1", 85.0)}
        seen = {pid: _make_seen(100.0)}
        events = compute_search_diff(listings, seen)
        assert len(events) == 1
        assert isinstance(events[0], PriceDrop)
        assert events[0].prop_id == pid
        assert events[0].previous_min == Decimal("100.0")
        assert events[0].listing.total_price == Decimal("85.0")

    def test_mixed_new_and_price_drop(self) -> None:
        pid_seen = str(uuid.uuid4())
        pid_new = str(uuid.uuid4())
        listings = {
            pid_seen: _make_listing("existing", 70.0),
            pid_new: _make_listing("brand_new", 200.0),
        }
        seen = {pid_seen: _make_seen(100.0)}
        events = compute_search_diff(listings, seen)
        assert len(events) == 2
        drop_events = [e for e in events if isinstance(e, PriceDrop)]
        new_events = [e for e in events if isinstance(e, NewListing)]
        assert len(drop_events) == 1
        assert len(new_events) == 1
        assert drop_events[0].previous_min == Decimal("100.0")
        assert new_events[0].prop_id == pid_new
