import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.notification_repository import get_notifications_page
from app.schemas.notification import NotificationListResponse, NotificationResponse

log = structlog.get_logger(__name__)


async def list_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    size: int = 50,
    notification_type: str | None = None,
) -> NotificationListResponse:
    rows, total = await get_notifications_page(
        db=db,
        user_id=user_id,
        page=page,
        size=size,
        notification_type=notification_type,
    )
    items = [
        NotificationResponse(
            id=log_row.id,
            type=log_row.type,
            property_name=prop_name,
            property_url=log_row.property_url,
            price_before=log_row.price_before,
            price_after=log_row.price_after,
            sent_at=log_row.sent_at,
            delivery_status=log_row.delivery_status,
        )
        for log_row, prop_name in rows
    ]
    pages = max(1, (total + size - 1) // size)
    return NotificationListResponse(items=items, total=total, page=page, size=size, pages=pages)
