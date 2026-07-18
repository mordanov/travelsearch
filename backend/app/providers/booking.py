"""
BookingProvider — Playwright-based scraper for Booking.com.
Scraper internals are encapsulated here; no other module imports this class directly.
"""

import re
from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import structlog

from app.core.config import get_settings
from app.providers.base import (
    ParsedPropertySearch,
    PropertyDetail,
    PropertyListing,
    Provider,
    ScrapeStatus,
    SearchResult,
)

log = structlog.get_logger(__name__)


class BookingProvider(Provider):
    async def search(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        guests: int,
        filters: dict,  # type: ignore[type-arg]
    ) -> SearchResult:
        try:
            return await self._do_search(destination, check_in, check_out, guests, filters)
        except Exception:
            log.exception("booking_search_error", destination=destination)
            return SearchResult(status=ScrapeStatus.BLOCKED, listings=[], provider="booking")

    async def _do_search(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        guests: int,
        filters: dict,  # type: ignore[type-arg]
    ) -> SearchResult:
        # Playwright scraping implementation
        # Uses proxy from settings, async browser context per call
        settings = get_settings()
        proxy = None
        if settings.proxy_provider_host:
            proxy = {
                "server": f"http://{settings.proxy_provider_host}",
                "username": settings.proxy_provider_user,
                "password": settings.proxy_provider_pass,
            }

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    proxy=proxy,  # type: ignore[arg-type]
                )
                try:
                    context = await browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        ),
                        viewport={"width": 1280, "height": 800},
                    )
                    page = await context.new_page()

                    check_in_str = check_in.strftime("%Y-%m-%d")
                    check_out_str = check_out.strftime("%Y-%m-%d")
                    url = (
                        f"https://www.booking.com/searchresults.html"
                        f"?ss={destination}&checkin={check_in_str}&checkout={check_out_str}"
                        f"&group_adults={guests}&no_rooms=1&lang=en-us"
                    )

                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")

                    # CAPTCHA / block detection
                    content = await page.content()
                    if self._is_blocked(content):
                        return SearchResult(
                            status=ScrapeStatus.BLOCKED, listings=[], provider="booking"
                        )

                    listings = await self._parse_search_results(page, check_in, check_out, guests)

                    if not listings:
                        return SearchResult(
                            status=ScrapeStatus.INCOMPLETE, listings=[], provider="booking"
                        )

                    return SearchResult(
                        status=ScrapeStatus.OK, listings=listings, provider="booking"
                    )
                finally:
                    await browser.close()

        except Exception as exc:
            log.warning("booking_playwright_error", error=str(exc))
            return SearchResult(status=ScrapeStatus.BLOCKED, listings=[], provider="booking")

    def _is_blocked(self, content: str) -> bool:
        block_signals = ["captcha", "robot", "blocked", "challenge", "Cloudflare"]
        return any(signal.lower() in content.lower() for signal in block_signals)

    async def _parse_search_results(
        self, page: object, check_in: date, check_out: date, guests: int
    ) -> list[PropertyListing]:
        listings = []
        try:
            p = page  # type: ignore[assignment]
            cards = await p.query_selector_all('[data-testid="property-card"]')  # type: ignore[attr-defined]
            nights = (check_out - check_in).days or 1

            for card in cards[:50]:
                try:
                    name_el = await card.query_selector('[data-testid="title"]')
                    name = (await name_el.inner_text()).strip() if name_el else ""
                    if not name:
                        continue

                    link_el = await card.query_selector('a[data-testid="title-link"]')
                    url = await link_el.get_attribute("href") if link_el else ""
                    url = url or ""
                    if url and not url.startswith("http"):
                        url = "https://www.booking.com" + url

                    price_el = await card.query_selector(
                        '[data-testid="price-and-discounted-price"]'
                    )
                    price_text = (await price_el.inner_text()).strip() if price_el else "0"
                    total_price = self._parse_price(price_text)
                    price_per_night = Decimal(str(round(float(total_price) / nights, 2)))

                    rating_el = await card.query_selector('[data-testid="review-score"]')
                    rating_text = (await rating_el.inner_text()).strip() if rating_el else ""
                    rating = self._parse_rating(rating_text)

                    provider_property_id = self._extract_hotel_id(url)
                    if not provider_property_id:
                        continue

                    listings.append(
                        PropertyListing(
                            provider="booking",
                            provider_property_id=provider_property_id,
                            name=name,
                            url=url,
                            price_per_night=price_per_night,
                            total_price=total_price,
                            rating=rating,
                            amenities=[],
                        )
                    )
                except Exception:
                    log.debug("booking_card_parse_error")
                    continue

        except Exception:
            log.exception("booking_parse_results_error")

        return listings

    def _parse_price(self, text: str) -> Decimal:
        digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return Decimal(digits) if digits else Decimal("0")
        except Exception:
            return Decimal("0")

    def _parse_rating(self, text: str) -> float | None:
        match = re.search(r"(\d+[.,]\d+)", text)
        if match:
            try:
                return float(match.group(1).replace(",", "."))
            except ValueError:
                pass
        return None

    def _extract_hotel_id(self, url: str) -> str:
        match = re.search(r"hotelid=(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"/hotel/[a-z]+/([^.?]+)\.html", url)
        if match:
            return match.group(1)
        return ""

    async def details(
        self,
        provider_property_id: str,
        check_in: date,
        check_out: date,
        guests: int,
    ) -> PropertyDetail:
        try:
            return await self._do_details(provider_property_id, check_in, check_out, guests)
        except Exception:
            log.exception("booking_details_error", property_id=provider_property_id)
            return PropertyDetail(status=ScrapeStatus.BLOCKED, listing=None, provider="booking")

    async def _do_details(
        self,
        provider_property_id: str,
        check_in: date,
        check_out: date,
        guests: int,
    ) -> PropertyDetail:
        settings = get_settings()
        proxy = None
        if settings.proxy_provider_host:
            proxy = {
                "server": f"http://{settings.proxy_provider_host}",
                "username": settings.proxy_provider_user,
                "password": settings.proxy_provider_pass,
            }

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, proxy=proxy)  # type: ignore[arg-type]
                try:
                    context = await browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
                        )
                    )
                    page = await context.new_page()

                    check_in_str = check_in.strftime("%Y-%m-%d")
                    check_out_str = check_out.strftime("%Y-%m-%d")
                    url = (
                        f"https://www.booking.com/hotel/xx/{provider_property_id}.html"
                        f"?checkin={check_in_str}&checkout={check_out_str}&group_adults={guests}"
                    )
                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")

                    content = await page.content()
                    if self._is_blocked(content):
                        return PropertyDetail(
                            status=ScrapeStatus.BLOCKED, listing=None, provider="booking"
                        )

                    price_el = await page.query_selector(
                        '[data-testid="price-and-discounted-price"]'
                    )
                    price_text = (await price_el.inner_text()).strip() if price_el else "0"
                    nights = (check_out - check_in).days or 1
                    total_price = self._parse_price(price_text)
                    price_per_night = Decimal(str(round(float(total_price) / nights, 2)))

                    name_el = await page.query_selector("h2.hp__hotel-name, h1.pp-header__title")
                    name = (await name_el.inner_text()).strip() if name_el else provider_property_id

                    listing = PropertyListing(
                        provider="booking",
                        provider_property_id=provider_property_id,
                        name=name,
                        url=url,
                        price_per_night=price_per_night,
                        total_price=total_price,
                        amenities=[],
                    )
                    return PropertyDetail(
                        status=ScrapeStatus.OK, listing=listing, provider="booking"
                    )
                finally:
                    await browser.close()

        except Exception as exc:
            log.warning("booking_details_playwright_error", error=str(exc))
            return PropertyDetail(status=ScrapeStatus.BLOCKED, listing=None, provider="booking")

    def parse_url(self, url: str) -> ParsedPropertySearch | None:
        try:
            parsed = urlparse(url)
            if "booking.com" not in parsed.netloc:
                return None

            qs = parse_qs(parsed.query)

            check_in_list = qs.get("checkin", [])
            check_out_list = qs.get("checkout", [])
            if not check_in_list or not check_out_list:
                return None

            from datetime import date as date_type

            check_in = date_type.fromisoformat(check_in_list[0])
            check_out = date_type.fromisoformat(check_out_list[0])
            guests_list = qs.get("group_adults", ["1"])
            guests = int(guests_list[0]) if guests_list else 1

            hotel_id = self._extract_hotel_id(url)
            if not hotel_id:
                return None

            return ParsedPropertySearch(
                provider="booking",
                provider_property_id=hotel_id,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
            )
        except Exception:
            return None

    def normalize(self, raw: dict) -> PropertyListing:  # type: ignore[type-arg]
        nights = raw.get("nights", 1) or 1
        total = Decimal(str(raw.get("total_price", 0)))
        return PropertyListing(
            provider="booking",
            provider_property_id=str(raw.get("id", "")),
            name=str(raw.get("name", "")),
            url=str(raw.get("url", "")),
            price_per_night=Decimal(str(round(float(total) / nights, 2))),
            total_price=total,
            rating=raw.get("rating"),
            bedrooms=raw.get("bedrooms"),
            bathrooms=raw.get("bathrooms"),
            distance_km=raw.get("distance_km"),
            free_cancellation=raw.get("free_cancellation"),
            amenities=raw.get("amenities", []),
            location=raw.get("location"),
            latitude=raw.get("latitude"),
            longitude=raw.get("longitude"),
        )
