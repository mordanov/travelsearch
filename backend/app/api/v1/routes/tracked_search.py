import uuid

import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import DB, CurrentUser
from app.repositories import tracking_repository
from app.repositories.search_repository import get_search
from app.schemas.tracked_search import (
    CreateTrackedSearchRequest,
    TrackedSearchListResponse,
    TrackedSearchResponse,
)
from app.services.tracking_service import (
    InvalidIntervalError,
    TrackingLimitExceededError,
    TrackingNotFoundError,
    create_tracked_search,
    remove_tracked_search,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/tracked-searches", tags=["tracked-searches"])


@router.post("", response_model=TrackedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create(
    body: CreateTrackedSearchRequest,
    current_user: CurrentUser,
    db: DB,
) -> TrackedSearchResponse:
    try:
        ts, warning = await create_tracked_search(
            db=db,
            user=current_user,
            search_id=body.search_id,
            interval_hours=body.interval_hours,
        )
        await db.commit()
    except (TrackingLimitExceededError, InvalidIntervalError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except TrackingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    search = await get_search(db, ts.search_id)
    assert search is not None

    return TrackedSearchResponse(
        id=ts.id,
        search_id=ts.search_id,
        destination=search.destination,
        check_in=search.check_in,
        check_out=search.check_out,
        interval_hours=ts.interval_hours,
        is_active=ts.is_active,
        last_successful_run_at=ts.last_successful_run_at,
        next_run_at=ts.next_run_at,
        telegram_warning=warning,
    )


@router.get("", response_model=TrackedSearchListResponse)
async def list_tracked(
    current_user: CurrentUser,
    db: DB,
) -> TrackedSearchListResponse:
    items_db = await tracking_repository.get_active_tracked_searches(db, current_user.id)
    items = []
    for ts in items_db:
        search = await get_search(db, ts.search_id)
        items.append(
            TrackedSearchResponse(
                id=ts.id,
                search_id=ts.search_id,
                destination=search.destination if search else "",
                check_in=search.check_in if search else ts.created_at,
                check_out=search.check_out if search else ts.created_at,
                interval_hours=ts.interval_hours,
                is_active=ts.is_active,
                last_successful_run_at=ts.last_successful_run_at,
                next_run_at=ts.next_run_at,
            )
        )
    return TrackedSearchListResponse(items=items, total=len(items))


@router.delete("/{tracked_search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tracked(
    tracked_search_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> None:
    try:
        await remove_tracked_search(db, current_user.id, tracked_search_id)
        await db.commit()
    except TrackingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
