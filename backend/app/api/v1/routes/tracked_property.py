import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import DB, CurrentUser
from app.repositories import tracking_repository
from app.repositories.property_repository import get_by_id as get_property_by_id
from app.schemas.tracked_property import (
    CreateTrackedPropertyRequest,
    TrackedPropertyListResponse,
    TrackedPropertyResponse,
)
from app.services.tracking_service import (
    InvalidIntervalError,
    TrackingLimitExceededError,
    TrackingNotFoundError,
    create_tracked_property,
    remove_tracked_property,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/tracked-properties", tags=["tracked-properties"])


@router.post("", response_model=TrackedPropertyResponse, status_code=status.HTTP_201_CREATED)
async def create(
    body: CreateTrackedPropertyRequest,
    current_user: CurrentUser,
    db: DB,
) -> TrackedPropertyResponse:
    check_in = datetime.combine(body.check_in, datetime.min.time())
    check_out = datetime.combine(body.check_out, datetime.min.time())

    try:
        tp, warning = await create_tracked_property(
            db=db,
            user=current_user,
            property_id=body.property_id,
            check_in=check_in,
            check_out=check_out,
            interval_hours=body.interval_hours,
        )
        await db.commit()
    except (TrackingLimitExceededError, InvalidIntervalError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except TrackingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return TrackedPropertyResponse(
        id=tp.id,
        property_id=tp.property_id,
        check_in=tp.check_in.date(),
        check_out=tp.check_out.date(),
        interval_hours=tp.interval_hours,
        is_active=tp.is_active,
        min_price_seen=tp.min_price_seen,
        last_successful_run_at=tp.last_successful_run_at,
        next_run_at=tp.next_run_at,
        telegram_warning=warning,
    )


@router.get("", response_model=TrackedPropertyListResponse)
async def list_tracked(
    current_user: CurrentUser,
    db: DB,
) -> TrackedPropertyListResponse:
    items_db = await tracking_repository.get_active_tracked_properties(db, current_user.id)
    items = [
        TrackedPropertyResponse(
            id=tp.id,
            property_id=tp.property_id,
            check_in=tp.check_in.date(),
            check_out=tp.check_out.date(),
            interval_hours=tp.interval_hours,
            is_active=tp.is_active,
            min_price_seen=tp.min_price_seen,
            last_successful_run_at=tp.last_successful_run_at,
            next_run_at=tp.next_run_at,
        )
        for tp in items_db
    ]
    return TrackedPropertyListResponse(items=items, total=len(items))


@router.delete("/{tracked_property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tracked(
    tracked_property_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> None:
    try:
        await remove_tracked_property(db, current_user.id, tracked_property_id)
        await db.commit()
    except TrackingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
