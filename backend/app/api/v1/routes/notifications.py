
import structlog
from fastapi import APIRouter, Query

from app.api.v1.deps import DB, CurrentUser
from app.schemas.notification import NotificationListResponse
from app.services.notification_service import list_notifications

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    current_user: CurrentUser,
    db: DB,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    type: str | None = Query(default=None),
) -> NotificationListResponse:
    return await list_notifications(
        db=db,
        user_id=current_user.id,
        page=page,
        size=size,
        notification_type=type,
    )
