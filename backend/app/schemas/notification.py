from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    property_name: str
    property_url: str
    price_before: Decimal | None = None
    price_after: Decimal
    sent_at: datetime
    delivery_status: str

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    size: int
    pages: int
