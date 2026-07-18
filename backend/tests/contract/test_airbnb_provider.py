"""Contract tests for AirbnbProvider against recorded fixtures."""
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.providers.base import ScrapeStatus
from app.providers.airbnb import AirbnbProvider


class TestAirbnbProviderContract:

    def test_parse_url_valid_airbnb_url(self) -> None:
        provider = AirbnbProvider()
        url = (
            "https://www.airbnb.com/rooms/12345678"
            "?checkin=2026-09-01&checkout=2026-09-07&adults=2"
        )
        result = provider.parse_url(url)
        assert result is not None
        assert result.provider == "airbnb"
        assert result.provider_property_id == "12345678"
        assert result.check_in == date(2026, 9, 1)
        assert result.check_out == date(2026, 9, 7)
        assert result.guests == 2

    def test_parse_url_missing_dates_returns_none(self) -> None:
        provider = AirbnbProvider()
        url = "https://www.airbnb.com/rooms/12345678"
        result = provider.parse_url(url)
        assert result is None

    def test_parse_url_non_airbnb_url_returns_none(self) -> None:
        provider = AirbnbProvider()
        url = "https://www.booking.com/hotel/es/test.html?checkin=2026-09-01&checkout=2026-09-07"
        result = provider.parse_url(url)
        assert result is None

    def test_normalize_maps_raw_dict(self) -> None:
        provider = AirbnbProvider()
        raw = {
            "id": "12345678",
            "name": "Airbnb Villa",
            "url": "https://airbnb.com/rooms/12345678",
            "total_price": 980,
            "nights": 7,
            "rating": 4.8,
            "amenities": ["wifi", "kitchen", "pool"],
        }
        listing = provider.normalize(raw)
        assert listing.provider == "airbnb"
        assert listing.provider_property_id == "12345678"
        assert float(listing.total_price) == 980.0
        assert float(listing.price_per_night) == 140.0
        assert listing.amenities == ["wifi", "kitchen", "pool"]

    @pytest.mark.asyncio
    async def test_search_returns_blocked_on_challenge(self) -> None:
        provider = AirbnbProvider()
        challenge_html = "<html><body>Please verify you are human — anti-bot check</body></html>"

        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value=challenge_html)
        mock_page.goto = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

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
        assert result.provider == "airbnb"
