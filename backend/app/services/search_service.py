import asyncio
import csv
import io
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import redis.asyncio as aioredis
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.base import Provider, ScrapeStatus
from app.repositories import property_repository, search_repository
from app.schemas.search import (
    PropertyListingResponse,
    ProviderStatus,
    SearchCreateResponse,
    SearchResultsPage,
    SearchStatusResponse,
)

log = structlog.get_logger(__name__)

SEARCH_STATUS_KEY = "search:status:{search_id}"


async def run_search(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: uuid.UUID,
    destination: str,
    check_in: date,
    check_out: date,
    guests: int,
    providers: list[str],
    filters: dict[str, Any],
    provider_registry: dict[str, Provider],
) -> SearchCreateResponse:
    from datetime import datetime

    search = await search_repository.create_search(
        db=db,
        user_id=user_id,
        destination=destination,
        check_in=datetime.combine(check_in, datetime.min.time()),
        check_out=datetime.combine(check_out, datetime.min.time()),
        guests=guests,
        providers=providers,
        filters=filters,
    )
    await db.commit()

    search_id = search.id
    await search_repository.update_status(db, search_id, "running")
    await db.commit()

    provider_results: dict[str, dict[str, Any]] = {}

    async def run_provider(pname: str) -> None:
        prov = provider_registry.get(pname)
        if prov is None:
            provider_results[pname] = {"status": "failed", "results": 0}
            return
        try:
            result = await prov.search(
                destination=destination,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                filters=filters,
            )
        except Exception:
            log.exception("provider_search_error", provider=pname)
            provider_results[pname] = {"status": "failed", "results": 0}
            return

        if result.status != ScrapeStatus.OK:
            provider_results[pname] = {"status": result.status.value, "results": 0}
            return

        results_to_add = []
        for listing in result.listings:
            prop = await property_repository.upsert_property(db, listing)
            results_to_add.append(
                {
                    "property_id": prop.id,
                    "price_per_night": float(listing.price_per_night),
                    "total_price": float(listing.total_price),
                    "rating": listing.rating,
                    "distance_km": listing.distance_km,
                    "free_cancellation": listing.free_cancellation,
                }
            )
        await search_repository.add_results(db, search_id, results_to_add)
        provider_results[pname] = {"status": "complete", "results": len(result.listings)}

    await asyncio.gather(*[run_provider(p) for p in providers])
    await db.commit()

    total = sum(v["results"] for v in provider_results.values())
    statuses = set(v["status"] for v in provider_results.values())

    if all(s == "complete" for s in statuses):
        final_status = "complete"
    elif any(s == "complete" for s in statuses):
        final_status = "partial"
    else:
        final_status = "failed"

    await search_repository.update_status(
        db,
        search_id,
        final_status,
        provider_statuses=provider_results,
        result_count=total,
    )
    await db.commit()

    return SearchCreateResponse(search_id=search_id, status=final_status)


async def get_status(
    db: AsyncSession,
    search_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SearchStatusResponse | None:
    search = await search_repository.get_search(db, search_id)
    # SEC-002: return None (→ 404) rather than 403 to avoid confirming resource existence
    if search is None or search.user_id != user_id:
        return None

    provider_statuses: dict[str, ProviderStatus] = {}
    if search.provider_statuses:
        for pname, pdata in search.provider_statuses.items():
            provider_statuses[pname] = ProviderStatus(
                status=pdata.get("status", "unknown"),
                results=pdata.get("results", 0),
            )

    return SearchStatusResponse(
        search_id=search_id,
        status=search.status,
        results_count=search.result_count or 0,
        provider_statuses=provider_statuses,
        destination=search.destination,
        check_in=search.check_in.date() if search.check_in else None,
        check_out=search.check_out.date() if search.check_out else None,
        guests=search.guests,
    )


async def get_results_page(
    db: AsyncSession,
    search_id: uuid.UUID,
    user_id: uuid.UUID,
    page: int = 1,
    size: int = 50,
    sort_by: str = "total_price",
    sort_dir: str = "asc",
    provider: str | None = None,
    price_max: float | None = None,
    rating_min: float | None = None,
    free_cancellation: bool | None = None,
) -> SearchResultsPage | None:
    # SEC-002: enforce ownership before returning results
    search = await search_repository.get_search(db, search_id)
    if search is None or search.user_id != user_id:
        return None

    rows, total = await search_repository.get_results_page(
        db=db,
        search_id=search_id,
        page=page,
        size=size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        provider=provider,
        price_max=price_max,
        rating_min=rating_min,
        free_cancellation=free_cancellation,
    )

    items = []
    for sr, prop in rows:
        amenities = await property_repository.get_amenities(prop)
        items.append(
            PropertyListingResponse(
                property_id=prop.id,
                provider=prop.provider,
                name=prop.name,
                price_per_night=Decimal(str(sr.price_per_night)),
                total_price=Decimal(str(sr.total_price)),
                rating=float(sr.rating) if sr.rating is not None else None,
                bedrooms=prop.bedrooms,
                bathrooms=prop.bathrooms,
                distance_km=float(sr.distance_km) if sr.distance_km is not None else None,
                free_cancellation=sr.free_cancellation,
                amenities=amenities,
                url=prop.url,
                location=prop.location,
            )
        )

    pages = max(1, (total + size - 1) // size)
    return SearchResultsPage(items=items, total=total, page=page, size=size, pages=pages)


async def export_csv(
    db: AsyncSession,
    search_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    # SEC-002: enforce ownership before exporting
    search = await search_repository.get_search(db, search_id)
    if search is None or search.user_id != user_id:
        return None

    rows, _ = await search_repository.get_results_page(db=db, search_id=search_id, size=10000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Provider",
            "Name",
            "Price/Night",
            "Total Price",
            "Rating",
            "Bedrooms",
            "Bathrooms",
            "Distance (km)",
            "Free Cancellation",
            "Location",
            "URL",
        ]
    )
    for sr, prop in rows:
        writer.writerow(
            [
                prop.provider,
                prop.name,
                sr.price_per_night,
                sr.total_price,
                sr.rating or "",
                prop.bedrooms or "",
                prop.bathrooms or "",
                sr.distance_km or "",
                sr.free_cancellation or "",
                prop.location or "",
                prop.url,
            ]
        )
    return output.getvalue()
