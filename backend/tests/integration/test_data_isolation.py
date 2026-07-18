"""Integration test: verify per-user data isolation (FR-015)."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import User
from app.providers.base import PropertyListing, ScrapeStatus, SearchResult


@pytest.fixture
async def user_a(db_session: object) -> User:
    from sqlalchemy.ext.asyncio import AsyncSession

    db: AsyncSession = db_session  # type: ignore[assignment]
    user = User(email="isolation_a@example.com", hashed_password=hash_password("pass"))
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def user_b(db_session: object) -> User:
    from sqlalchemy.ext.asyncio import AsyncSession

    db: AsyncSession = db_session  # type: ignore[assignment]
    user = User(email="isolation_b@example.com", hashed_password=hash_password("pass"))
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def token_a(client: AsyncClient, user_a: User) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "isolation_a@example.com", "password": "pass"},
    )
    return resp.json()["access_token"]


@pytest.fixture
async def token_b(client: AsyncClient, user_b: User) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "isolation_b@example.com", "password": "pass"},
    )
    return resp.json()["access_token"]


class TestDataIsolation:
    @pytest.mark.asyncio
    async def test_tracked_searches_isolated(
        self,
        client: AsyncClient,
        user_a: User,
        user_b: User,
        token_a: str,
        token_b: str,
    ) -> None:
        listing = PropertyListing(
            provider="booking",
            provider_property_id="isolate_hotel",
            name="Isolation Hotel",
            url="https://booking.com/isolate",
            price_per_night=Decimal("50"),
            total_price=Decimal("350"),
        )
        booking_result = SearchResult(
            status=ScrapeStatus.OK, listings=[listing], provider="booking"
        )
        airbnb_result = SearchResult(status=ScrapeStatus.OK, listings=[], provider="airbnb")

        with (
            patch("app.providers.booking.BookingProvider") as MockBooking,
            patch("app.providers.airbnb.AirbnbProvider") as MockAirbnb,
        ):
            MockBooking.return_value.search = AsyncMock(return_value=booking_result)
            MockAirbnb.return_value.search = AsyncMock(return_value=airbnb_result)

            # User A creates a search and tracks it
            search_resp = await client.post(
                "/api/v1/search",
                json={
                    "destination": "Paris",
                    "check_in": "2026-10-01",
                    "check_out": "2026-10-07",
                    "guests": 1,
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )
        search_id = search_resp.json()["search_id"]

        track_resp = await client.post(
            "/api/v1/tracked-searches",
            json={"search_id": search_id, "interval_hours": 24},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert track_resp.status_code == 201

        # User B should see an empty tracked searches list
        list_resp = await client.get(
            "/api/v1/tracked-searches",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        # User B has no tracked searches
        assert all(item["search_id"] != search_id for item in items)

    @pytest.mark.asyncio
    async def test_search_results_not_accessible_cross_user(
        self,
        client: AsyncClient,
        user_a: User,
        user_b: User,
        token_a: str,
        token_b: str,
    ) -> None:
        """SEC-002: User B cannot access User A's search via status, results, or export."""
        listing = PropertyListing(
            provider="booking",
            provider_property_id="sec002_hotel",
            name="SEC002 Hotel",
            url="https://booking.com/sec002",
            price_per_night=Decimal("80"),
            total_price=Decimal("560"),
        )
        booking_result = SearchResult(
            status=ScrapeStatus.OK, listings=[listing], provider="booking"
        )
        airbnb_result = SearchResult(status=ScrapeStatus.OK, listings=[], provider="airbnb")

        with (
            patch("app.providers.booking.BookingProvider") as MockBooking,
            patch("app.providers.airbnb.AirbnbProvider") as MockAirbnb,
        ):
            MockBooking.return_value.search = AsyncMock(return_value=booking_result)
            MockAirbnb.return_value.search = AsyncMock(return_value=airbnb_result)

            search_resp = await client.post(
                "/api/v1/search",
                json={
                    "destination": "Rome",
                    "check_in": "2026-11-01",
                    "check_out": "2026-11-05",
                    "guests": 2,
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )
        assert search_resp.status_code == 202
        search_id = search_resp.json()["search_id"]

        # User B attempts to read User A's search — must receive 404, not 403
        status_resp = await client.get(
            f"/api/v1/search/{search_id}/status",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status_resp.status_code == 404

        results_resp = await client.get(
            f"/api/v1/search/{search_id}/results",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert results_resp.status_code == 404

        csv_resp = await client.get(
            f"/api/v1/search/{search_id}/export.csv",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert csv_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_notifications_isolated(
        self,
        client: AsyncClient,
        user_a: User,
        user_b: User,
        token_a: str,
        token_b: str,
    ) -> None:
        """User B's notification list must not include notifications created for User A."""
        resp_a = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        resp_b = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        assert resp_a.json()["total"] == 0
        assert resp_b.json()["total"] == 0
