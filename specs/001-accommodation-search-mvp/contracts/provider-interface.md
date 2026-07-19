# Provider & Notifier Interfaces

**Branch**: `001-accommodation-search-mvp` | **Date**: 2026-07-19

These typed interfaces are the Constitution I contract boundary. The backend MUST only
communicate with providers and notifiers through these interfaces. No backend code may
import or call any provider or notifier implementation directly.

---

## Provider (Accommodation)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class ScrapeStatus(str, Enum):
    OK = "ok"
    BLOCKED = "blocked"
    CAPTCHA = "captcha"
    INCOMPLETE = "incomplete"


@dataclass
class PropertyListing:
    provider: str                     # 'booking' | 'airbnb'
    provider_property_id: str
    name: str
    url: str
    price_per_night: Decimal
    total_price: Decimal
    rating: Optional[float]
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    distance_km: Optional[float]
    free_cancellation: Optional[bool]
    amenities: list[str]
    location: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]


@dataclass
class SearchResult:
    status: ScrapeStatus
    listings: list[PropertyListing]   # empty if status != OK
    provider: str


@dataclass
class PropertyDetail:
    status: ScrapeStatus
    listing: Optional[PropertyListing]  # None if status != OK
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
        filters: dict,
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
    def parse_url(self, url: str) -> Optional[ParsedPropertySearch]:
        """
        Parse a provider URL and extract property identity + dates.
        Returns None if the URL is not a recognized listing or lacks date params.
        Pure function — no network calls.
        """
        ...

    @abstractmethod
    def normalize(self, raw: dict) -> PropertyListing:
        """
        Normalize a raw scraped payload to a PropertyListing.
        Called internally by search() and details().
        """
        ...
```

---

## Notifier

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import UUID


class NotificationType(str, Enum):
    NEW_LISTING = "new_listing"
    PRICE_DROP = "price_drop"


@dataclass
class NotificationMessage:
    type: NotificationType
    property_name: str
    property_url: str
    price_after: Decimal
    price_before: Optional[Decimal]   # None for new_listing


class Notifier(ABC):

    @abstractmethod
    async def send(
        self,
        telegram_chat_id: int,
        message: NotificationMessage,
    ) -> bool:
        """
        Send a notification to the user's Telegram chat.
        Returns True on success, False on delivery failure.
        MUST NOT raise — encode failure in return value.
        """
        ...
```

---

## Contract Rules

1. `Provider.search()` and `Provider.details()` MUST encode all scraping failures in
   `ScrapeStatus` — never raise exceptions for blocked/CAPTCHA/incomplete states.
2. Workers MUST check `result.status == ScrapeStatus.OK` before any diff or DB write.
   A non-OK status triggers safe discard with a structured log entry.
3. `Notifier.send()` MUST NOT raise — the worker logs delivery failures and continues.
4. `Provider.parse_url()` is synchronous and pure — called in the Telegram bot handler
   to validate `/follow` URLs before any async operation.
5. No backend module outside `app/providers/` may import `BookingProvider` or
   `AirbnbProvider`. No backend module outside `app/notifiers/` may import
   `TelegramNotifier`.
