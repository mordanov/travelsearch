import uuid
from collections.abc import Iterator
from typing import Literal

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.v1.deps import DB, CurrentUser, Redis
from app.providers.base import Provider
from app.schemas.search import (
    SearchCreateResponse,
    SearchRequest,
    SearchResultsPage,
    SearchStatusResponse,
)
from app.services import search_service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


def _get_provider_registry() -> dict[str, Provider]:
    # Providers registered here; route imports only the base interface (constitution I)
    from app.providers.airbnb import AirbnbProvider
    from app.providers.booking import BookingProvider

    return {
        "booking": BookingProvider(),
        "airbnb": AirbnbProvider(),
    }


@router.post("", response_model=SearchCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_search(
    body: SearchRequest,
    current_user: CurrentUser,
    db: DB,
    redis: Redis,
) -> SearchCreateResponse:
    if body.check_out <= body.check_in:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="check_out must be after check_in",
        )
    registry = _get_provider_registry()
    result = await search_service.run_search(
        db=db,
        redis=redis,
        user_id=current_user.id,
        destination=body.destination,
        check_in=body.check_in,
        check_out=body.check_out,
        guests=body.guests,
        providers=list(body.providers),
        filters=body.filters.model_dump(exclude_none=True),
        provider_registry=registry,
    )
    return result


@router.get("/{search_id}/status", response_model=SearchStatusResponse)
async def get_search_status(
    search_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> SearchStatusResponse:
    # SEC-002: user_id passed — service returns None if not owned (→ 404, not 403)
    result = await search_service.get_status(db, search_id, current_user.id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    return result


@router.get("/{search_id}/results", response_model=SearchResultsPage)
async def get_search_results(
    search_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    sort_by: str = Query(default="total_price"),
    sort_dir: Literal["asc", "desc"] = Query(default="asc"),
    provider: str | None = Query(default=None),
    price_max: float | None = Query(default=None),
    rating_min: float | None = Query(default=None),
    free_cancellation: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
) -> SearchResultsPage:
    # SEC-002: user_id passed — returns None if not owned
    result = await search_service.get_results_page(
        db=db,
        search_id=search_id,
        user_id=current_user.id,
        page=page,
        size=size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        provider=provider,
        price_max=price_max,
        rating_min=rating_min,
        free_cancellation=free_cancellation,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    return result


@router.get("/{search_id}/export.csv")
async def export_csv(
    search_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> StreamingResponse:
    # SEC-002: user_id passed — returns None if not owned
    csv_content = await search_service.export_csv(db, search_id, current_user.id)
    if csv_content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")

    def _iter() -> Iterator[str]:
        yield csv_content

    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=search-{search_id}.csv"},
    )
