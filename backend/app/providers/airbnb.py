"""
AirbnbProvider — Playwright-based scraper for Airbnb.
Scraper internals are encapsulated here; no other module imports this class directly.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from urllib.parse import urlparse, parse_qs
import re

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


class AirbnbProvider(Provider):

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
            log.exception("airbnb_search_error", destination=destination)
            return SearchResult(status=ScrapeStatus.BLOCKED, listings=[], provider="airbnb")

    async def _do_search(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        guests: int,
        filters: dict,  # type: ignore[type-arg]
    ) -> SearchResult:
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
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        ),
                        viewport={"width": 1440, "height": 900},
                        locale="en-US",
                    )
                    page = await context.new_page()

                    check_in_str = check_in.strftime("%Y-%m-%d")
                    check_out_str = check_out.strftime("%Y-%m-%d")
                    url = (
                        f"https://www.airbnb.com/s/{destination}/homes"
                        f"?checkin={check_in_str}&checkout={check_out_str}&adults={guests}"
                    )

                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)

                    content = await page.content()
                    if self._is_blocked(content):
                        return SearchResult(status=ScrapeStatus.BLOCKED, listings=[], provider="airbnb")

                    listings = await self._parse_search_results(page, check_in, check_out, guests)

                    if not listings:
                        return SearchResult(
                            status=ScrapeStatus.INCOMPLETE, listings=[], provider="airbnb"
                        )

                    return SearchResult(status=ScrapeStatus.OK, listings=listings, provider="airbnb")
                finally:
                    await browser.close()

        except Exception as exc:
            log.warning("airbnb_playwright_error", error=str(exc))
            return SearchResult(status=ScrapeStatus.BLOCKED, listings=[], provider="airbnb")

    def _is_blocked(self, content: str) -> bool:
        signals = ["captcha", "robot", "blocked", "anti-bot", "verify you are human"]
        return any(s in content.lower() for s in signals)

    async def _parse_search_results(
        self, page: object, check_in: date, check_out: date, guests: int
    ) -> list[PropertyListing]:
        listings = []
        nights = (check_out - check_in).days or 1
        try:
            p = page  # type: ignore[assignment]
            cards = await p.query_selector_all('[itemprop="itemListElement"]')  # type: ignore[attr-defined]

            for card in cards[:50]:
                try:
                    name_el = await card.query_selector('[data-testid="listing-card-title"]')
                    if not name_el:
                        name_el = await card.query_selector("div[id^='title_']")
                    name = (await name_el.inner_text()).strip() if name_el else ""
                    if not name:
                        continue

                    link_el = await card.query_selector("a")
                    href = await link_el.get_attribute("href") if link_el else ""
                    href = href or ""
                    if href and not href.startswith("http"):
                        href = "https://www.airbnb.com" + href
                    room_id = self._extract_room_id(href)
                    if not room_id:
                        continue

                    price_el = await card.query_selector('span[data-testid="price-availability-row"]')
                    if not price_el:
                        price_el = await card.query_selector('div._1jo4hgw')
                    price_text = (await price_el.inner_text()).strip() if price_el else "0"
                    total_price = self._parse_price(price_text)
                    price_per_night = Decimal(str(round(float(total_price) / nights, 2)))

                    listings.append(
                        PropertyListing(
                            provider="airbnb",
                            provider_property_id=room_id,
                            name=name,
                            url=href,
                            price_per_night=price_per_night,
                            total_price=total_price,
                            amenities=[],
                        )
                    )
                except Exception:
                    log.debug("airbnb_card_parse_error")
                    continue

        except Exception:
            log.exception("airbnb_parse_results_error")

        return listings

    def _extract_room_id(self, url: str) -> str:
        match = re.search(r"/rooms/(\d+)", url)
        return match.group(1) if match else ""

    def _parse_price(self, text: str) -> Decimal:
        digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return Decimal(digits) if digits else Decimal("0")
        except Exception:
            return Decimal("0")

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
            log.exception("airbnb_details_error", property_id=provider_property_id)
            return PropertyDetail(status=ScrapeStatus.BLOCKED, listing=None, provider="airbnb")

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
                    context = await browser.new_context(locale="en-US")
                    page = await context.new_page()

                    check_in_str = check_in.strftime("%Y-%m-%d")
                    check_out_str = check_out.strftime("%Y-%m-%d")
                    url = (
                        f"https://www.airbnb.com/rooms/{provider_property_id}"
                        f"?checkin={check_in_str}&checkout={check_out_str}&adults={guests}"
                    )
                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)

                    content = await page.content()
                    if self._is_blocked(content):
                        return PropertyDetail(
                            status=ScrapeStatus.BLOCKED, listing=None, provider="airbnb"
                        )

                    nights = (check_out - check_in).days or 1
                    price_el = await page.query_selector('div._1ju0tuo')
                    price_text = (await price_el.inner_text()).strip() if price_el else "0"
                    total_price = self._parse_price(price_text)
                    price_per_night = Decimal(str(round(float(total_price) / nights, 2)))

                    name_el = await page.query_selector("h1")
                    name = (await name_el.inner_text()).strip() if name_el else provider_property_id

                    listing = PropertyListing(
                        provider="airbnb",
                        provider_property_id=provider_property_id,
                        name=name,
                        url=url,
                        price_per_night=price_per_night,
                        total_price=total_price,
                        amenities=[],
                    )
                    return PropertyDetail(status=ScrapeStatus.OK, listing=listing, provider="airbnb")
                finally:
                    await browser.close()

        except Exception as exc:
            log.warning("airbnb_details_playwright_error", error=str(exc))
            return PropertyDetail(status=ScrapeStatus.BLOCKED, listing=None, provider="airbnb")

    def parse_url(self, url: str) -> Optional[ParsedPropertySearch]:
        try:
            parsed = urlparse(url)
            if "airbnb.com" not in parsed.netloc:
                return None

            room_id = self._extract_room_id(url)
            if not room_id:
                return None

            qs = parse_qs(parsed.query)
            check_in_list = qs.get("checkin", [])
            check_out_list = qs.get("checkout", [])
            if not check_in_list or not check_out_list:
                return None

            from datetime import date as date_type

            check_in = date_type.fromisoformat(check_in_list[0])
            check_out = date_type.fromisoformat(check_out_list[0])
            adults_list = qs.get("adults", ["1"])
            guests = int(adults_list[0]) if adults_list else 1

            return ParsedPropertySearch(
                provider="airbnb",
                provider_property_id=room_id,
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
            provider="airbnb",
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
