"""Integration tests for TrackedSearch API."""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.search import Search
from app.models.user import User
from app.providers.base import PropertyListing, SearchResult, ScrapeStatus


@pytest.fixture
async def test_user2(db_session: object) -> User:
    from sqlalchemy.ext.asyncio import AsyncSession

    db: AsyncSession = db_session  # type: ignore[assignment]
    user = User(email="tracked_test@example.com", hashed_password=hash_password("testpass"))
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def auth_token2(client: AsyncClient, test_user2: User) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "tracked_test@example.com", "password": "testpass"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
async def search_id(client: AsyncClient, auth_token2: str) -> str:
    listing = PropertyListing(
        provider="booking",
        provider_property_id="bk_track_test",
        name="Track Test Hotel",
        url="https://booking.com/track_test",
        price_per_night=Decimal("100"),
        total_price=Decimal("700"),
    )
    booking_result = SearchResult(status=ScrapeStatus.OK, listings=[listing], provider="booking")
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
                "destination": "Berlin",
                "check_in": "2026-09-01",
                "check_out": "2026-09-07",
                "guests": 1,
            },
            headers={"Authorization": f"Bearer {auth_token2}"},
        )
    assert resp.status_code == 202
    return resp.json()["search_id"]


class TestTrackedSearchAPI:

    @pytest.mark.asyncio
    async def test_create_tracked_search(
        self, client: AsyncClient, test_user2: User, auth_token2: str, search_id: str
    ) -> None:
        resp = await client.post(
            "/api/v1/tracked-searches",
            json={"search_id": search_id, "interval_hours": 24},
            headers={"Authorization": f"Bearer {auth_token2}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["search_id"] == search_id
        assert data["interval_hours"] == 24
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_tracked_searches(
        self, client: AsyncClient, test_user2: User, auth_token2: str, search_id: str
    ) -> None:
        await client.post(
            "/api/v1/tracked-searches",
            json={"search_id": search_id, "interval_hours": 12},
            headers={"Authorization": f"Bearer {auth_token2}"},
        )
        resp = await client.get(
            "/api/v1/tracked-searches",
            headers={"Authorization": f"Bearer {auth_token2}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_delete_tracked_search(
        self, client: AsyncClient, test_user2: User, auth_token2: str, search_id: str
    ) -> None:
        create_resp = await client.post(
            "/api/v1/tracked-searches",
            json={"search_id": search_id, "interval_hours": 24},
            headers={"Authorization": f"Bearer {auth_token2}"},
        )
        ts_id = create_resp.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/tracked-searches/{ts_id}",
            headers={"Authorization": f"Bearer {auth_token2}"},
        )
        assert del_resp.status_code == 204

    @pytest.mark.asyncio
    async def test_invalid_interval_returns_422(
        self, client: AsyncClient, test_user2: User, auth_token2: str, search_id: str
    ) -> None:
        resp = await client.post(
            "/api/v1/tracked-searches",
            json={"search_id": search_id, "interval_hours": 7},
            headers={"Authorization": f"Bearer {auth_token2}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_notifications_empty(
        self, client: AsyncClient, test_user2: User, auth_token2: str
    ) -> None:
        resp = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {auth_token2}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
