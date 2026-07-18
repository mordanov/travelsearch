"""Integration tests for search API."""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import User
from app.providers.base import PropertyListing, SearchResult, ScrapeStatus


def _make_listing(name: str, provider: str = "booking") -> PropertyListing:
    return PropertyListing(
        provider=provider,
        provider_property_id=f"{provider}_{name.lower().replace(' ', '_')}",
        name=name,
        url=f"https://{provider}.com/{name}",
        price_per_night=Decimal("100"),
        total_price=Decimal("700"),
        rating=4.5,
        amenities=["wifi"],
    )


@pytest.fixture
async def test_user(db_session: object) -> User:
    from sqlalchemy.ext.asyncio import AsyncSession

    db: AsyncSession = db_session  # type: ignore[assignment]
    user = User(email="search_test@example.com", hashed_password=hash_password("testpass"))
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def auth_token(client: AsyncClient, test_user: User) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "search_test@example.com", "password": "testpass"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


class TestSearchAPI:

    @pytest.mark.asyncio
    async def test_search_returns_202(
        self, client: AsyncClient, test_user: User, auth_token: str
    ) -> None:
        booking_result = SearchResult(
            status=ScrapeStatus.OK,
            listings=[_make_listing("Barcelona Apt", "booking")],
            provider="booking",
        )
        airbnb_result = SearchResult(
            status=ScrapeStatus.OK,
            listings=[_make_listing("Gracia Room", "airbnb")],
            provider="airbnb",
        )

        with (
            patch("app.providers.booking.BookingProvider") as MockBooking,
            patch("app.providers.airbnb.AirbnbProvider") as MockAirbnb,
        ):
            MockBooking.return_value.search = AsyncMock(return_value=booking_result)
            MockAirbnb.return_value.search = AsyncMock(return_value=airbnb_result)

            resp = await client.post(
                "/api/v1/search",
                json={
                    "destination": "Barcelona",
                    "check_in": "2026-09-01",
                    "check_out": "2026-09-07",
                    "guests": 2,
                    "providers": ["booking", "airbnb"],
                },
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "search_id" in data
        assert data["status"] in ("complete", "partial", "failed", "running")

    @pytest.mark.asyncio
    async def test_search_status_polling(
        self, client: AsyncClient, test_user: User, auth_token: str
    ) -> None:
        booking_result = SearchResult(
            status=ScrapeStatus.OK, listings=[_make_listing("Apt 1")], provider="booking"
        )
        airbnb_result = SearchResult(
            status=ScrapeStatus.BLOCKED, listings=[], provider="airbnb"
        )

        with (
            patch("app.providers.booking.BookingProvider") as MockBooking,
            patch("app.providers.airbnb.AirbnbProvider") as MockAirbnb,
        ):
            MockBooking.return_value.search = AsyncMock(return_value=booking_result)
            MockAirbnb.return_value.search = AsyncMock(return_value=airbnb_result)

            resp = await client.post(
                "/api/v1/search",
                json={
                    "destination": "Madrid",
                    "check_in": "2026-10-01",
                    "check_out": "2026-10-07",
                    "guests": 1,
                    "providers": ["booking", "airbnb"],
                },
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert resp.status_code == 202
        search_id = resp.json()["search_id"]

        status_resp = await client.get(
            f"/api/v1/search/{search_id}/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["search_id"] == search_id

    @pytest.mark.asyncio
    async def test_search_results_pagination(
        self, client: AsyncClient, test_user: User, auth_token: str
    ) -> None:
        listings = [_make_listing(f"Hotel {i}") for i in range(5)]
        booking_result = SearchResult(status=ScrapeStatus.OK, listings=listings, provider="booking")
        airbnb_result = SearchResult(status=ScrapeStatus.OK, listings=[], provider="airbnb")

        with (
            patch("app.providers.booking.BookingProvider") as MockBooking,
            patch("app.providers.airbnb.AirbnbProvider") as MockAirbnb,
        ):
            MockBooking.return_value.search = AsyncMock(return_value=booking_result)
            MockAirbnb.return_value.search = AsyncMock(return_value=airbnb_result)

            resp = await client.post(
                "/api/v1/search",
                json={
                    "destination": "Rome",
                    "check_in": "2026-11-01",
                    "check_out": "2026-11-08",
                    "guests": 2,
                },
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        search_id = resp.json()["search_id"]
        results_resp = await client.get(
            f"/api/v1/search/{search_id}/results?page=1&size=10",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert results_resp.status_code == 200
        data = results_resp.json()
        assert "items" in data
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_csv_export(
        self, client: AsyncClient, test_user: User, auth_token: str
    ) -> None:
        listing = _make_listing("CSV Test Hotel")
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

            resp = await client.post(
                "/api/v1/search",
                json={
                    "destination": "Lisbon",
                    "check_in": "2026-12-01",
                    "check_out": "2026-12-07",
                    "guests": 1,
                },
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        search_id = resp.json()["search_id"]
        csv_resp = await client.get(
            f"/api/v1/search/{search_id}/export.csv",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers.get("content-type", "")
