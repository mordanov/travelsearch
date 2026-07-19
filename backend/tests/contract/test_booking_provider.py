"""Contract tests for BookingProvider against recorded fixtures."""

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.providers.base import ScrapeStatus
from app.providers.booking import BookingProvider

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "booking"


class TestBookingProviderContract:
    def test_parse_url_valid_booking_url(self) -> None:
        provider = BookingProvider()
        url = (
            "https://www.booking.com/hotel/es/gothic-quarter-apt.html"
            "?checkin=2026-09-01&checkout=2026-09-07&group_adults=2&hotelid=12345"
        )
        result = provider.parse_url(url)
        assert result is not None
        assert result.provider == "booking"
        assert result.check_in == date(2026, 9, 1)
        assert result.check_out == date(2026, 9, 7)
        assert result.guests == 2

    def test_parse_url_missing_dates_returns_none(self) -> None:
        provider = BookingProvider()
        url = "https://www.booking.com/hotel/es/gothic-quarter.html"
        result = provider.parse_url(url)
        assert result is None

    def test_parse_url_non_booking_url_returns_none(self) -> None:
        provider = BookingProvider()
        url = "https://www.airbnb.com/rooms/12345?checkin=2026-09-01&checkout=2026-09-07"
        result = provider.parse_url(url)
        assert result is None

    def test_normalize_maps_raw_dict(self) -> None:
        provider = BookingProvider()
        raw = {
            "id": "hotel123",
            "name": "Test Hotel",
            "url": "https://booking.com/hotel123",
            "total_price": 700,
            "nights": 7,
            "rating": 4.5,
            "bedrooms": 2,
            "amenities": ["wifi", "pool"],
            "location": "Barcelona",
        }
        listing = provider.normalize(raw)
        assert listing.provider == "booking"
        assert listing.provider_property_id == "hotel123"
        assert listing.name == "Test Hotel"
        assert float(listing.total_price) == 700.0
        assert float(listing.price_per_night) == 100.0
        assert listing.rating == 4.5
        assert listing.amenities == ["wifi", "pool"]

    @pytest.mark.asyncio
    async def test_search_blocked_returns_blocked_status(self) -> None:
        provider = BookingProvider()
        challenge_html = "<html><body>Captcha challenge — prove you're not a robot</body></html>"

        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value=challenge_html)
        mock_page.goto = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright_cm = AsyncMock()
        mock_playwright_cm.__aenter__ = AsyncMock(return_value=mock_playwright)
        mock_playwright_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("playwright.async_api.async_playwright", return_value=mock_playwright_cm):
            result = await provider.search(
                destination="Barcelona",
                check_in=date(2026, 9, 1),
                check_out=date(2026, 9, 7),
                guests=2,
                filters={},
            )

        assert result.status == ScrapeStatus.BLOCKED
        assert result.listings == []
        assert result.provider == "booking"
