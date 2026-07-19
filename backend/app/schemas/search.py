from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    price_max: float | None = None
    bedrooms_min: int | None = None
    bathrooms_min: int | None = None
    rating_min: float | None = None
    free_cancellation: bool | None = None
    amenities: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    destination: str = Field(min_length=1, max_length=500)
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=30)
    providers: list[Literal["booking", "airbnb"]] = Field(default=["booking", "airbnb"])
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchCreateResponse(BaseModel):
    search_id: UUID
    status: str


class ProviderStatus(BaseModel):
    status: str
    results: int


class SearchStatusResponse(BaseModel):
    search_id: UUID
    status: str
    results_count: int
    provider_statuses: dict[str, ProviderStatus]
    destination: str | None = None
    check_in: date | None = None
    check_out: date | None = None
    guests: int | None = None


class PropertyListingResponse(BaseModel):
    property_id: UUID
    provider: str
    name: str
    price_per_night: Decimal
    total_price: Decimal
    rating: float | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    distance_km: float | None = None
    free_cancellation: bool | None = None
    amenities: list[str] = Field(default_factory=list)
    url: str
    location: str | None = None


class SearchResultsPage(BaseModel):
    items: list[PropertyListingResponse]
    total: int
    page: int
    size: int
    pages: int
