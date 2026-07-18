import uuid
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.models.search import Search, SearchResult

log = structlog.get_logger(__name__)


async def create_search(
    db: AsyncSession,
    user_id: uuid.UUID,
    destination: str,
    check_in: datetime,
    check_out: datetime,
    guests: int,
    providers: list[str],
    filters: dict[str, Any] | None,
) -> Search:
    search = Search(
        user_id=user_id,
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        providers=providers,
        filters=filters,
        status="pending",
    )
    db.add(search)
    await db.flush()
    return search


async def update_status(
    db: AsyncSession,
    search_id: uuid.UUID,
    status: str,
    provider_statuses: dict[str, Any] | None = None,
    result_count: int | None = None,
) -> None:
    result = await db.execute(select(Search).where(Search.id == search_id))
    search = result.scalar_one_or_none()
    if search is None:
        return
    search.status = status
    if provider_statuses is not None:
        search.provider_statuses = provider_statuses
    if result_count is not None:
        search.result_count = result_count
    if status in ("complete", "failed", "partial"):
        search.completed_at = datetime.utcnow()
    await db.flush()


async def add_results(
    db: AsyncSession,
    search_id: uuid.UUID,
    results: list[dict[str, Any]],
) -> None:
    for r in results:
        row = SearchResult(
            search_id=search_id,
            property_id=r["property_id"],
            price_per_night=r["price_per_night"],
            total_price=r["total_price"],
            rating=r.get("rating"),
            distance_km=r.get("distance_km"),
            free_cancellation=r.get("free_cancellation"),
            raw_snapshot=r.get("raw_snapshot"),
        )
        db.add(row)
    await db.flush()


async def get_results_page(
    db: AsyncSession,
    search_id: uuid.UUID,
    page: int = 1,
    size: int = 50,
    sort_by: str = "total_price",
    sort_dir: str = "asc",
    provider: str | None = None,
    price_max: float | None = None,
    rating_min: float | None = None,
    free_cancellation: bool | None = None,
) -> tuple[list[tuple[SearchResult, Property]], int]:
    stmt = (
        select(SearchResult, Property)
        .join(Property, Property.id == SearchResult.property_id)
        .where(SearchResult.search_id == search_id)
    )

    if provider is not None:
        stmt = stmt.where(Property.provider == provider)
    if price_max is not None:
        stmt = stmt.where(SearchResult.total_price <= price_max)
    if rating_min is not None:
        stmt = stmt.where(SearchResult.rating >= rating_min)
    if free_cancellation is not None:
        stmt = stmt.where(SearchResult.free_cancellation == free_cancellation)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    sort_col = {
        "total_price": SearchResult.total_price,
        "price_per_night": SearchResult.price_per_night,
        "rating": SearchResult.rating,
        "distance_km": SearchResult.distance_km,
        "name": Property.name,
    }.get(sort_by, SearchResult.total_price)

    if sort_dir == "desc":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    rows = result.fetchall()
    return [(r[0], r[1]) for r in rows], total


async def get_search(db: AsyncSession, search_id: uuid.UUID) -> Search | None:
    result = await db.execute(select(Search).where(Search.id == search_id))
    return result.scalar_one_or_none()
