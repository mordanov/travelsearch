from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class ScrapeStatus(StrEnum):
    OK = "ok"
    BLOCKED = "blocked"
    CAPTCHA = "captcha"
    INCOMPLETE = "incomplete"


@dataclass
class PropertyListing:
    provider: str
    provider_property_id: str
    name: str
    url: str
    price_per_night: Decimal
    total_price: Decimal
    rating: float | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    distance_km: float | None = None
    free_cancellation: bool | None = None
    amenities: list[str] = field(default_factory=list)
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass
class SearchResult:
    status: ScrapeStatus
    listings: list[PropertyListing]
    provider: str


@dataclass
class PropertyDetail:
    status: ScrapeStatus
    listing: PropertyListing | None
    provider: str


@dataclass
class ParsedPropertySearch:
    provider: str
    provider_property_id: str
    check_in: date
    check_out: date
    guests: int


class Provider(ABC):

    @abstractmethod
    async def search(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        guests: int,
        filters: dict,  # type: ignore[type-arg]
    ) -> SearchResult:
        """
        Scrape accommodation listings for the given criteria.
        Returns SearchResult with status=OK and listings, or
        status=BLOCKED/CAPTCHA/INCOMPLETE with empty listings.
        MUST NOT raise on scraping failure — encode failure in status.
        """
        ...

    @abstractmethod
    async def details(
        self,
        provider_property_id: str,
        check_in: date,
        check_out: date,
        guests: int,
    ) -> PropertyDetail:
        """
        Fetch current price and details for a specific property.
        Returns PropertyDetail with status=OK and listing, or
        status=BLOCKED/CAPTCHA/INCOMPLETE with listing=None.
        """
        ...

    @abstractmethod
    def parse_url(self, url: str) -> ParsedPropertySearch | None:
        """
        Parse a provider URL and extract property identity + dates.
        Returns None if the URL is not a recognized listing or lacks date params.
        Pure function — no network calls.
        """
        ...

    @abstractmethod
    def normalize(self, raw: dict) -> PropertyListing:  # type: ignore[type-arg]
        """
        Normalize a raw scraped payload to a PropertyListing.
        Called internally by search() and details().
        """
        ...
