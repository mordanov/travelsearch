from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class CreateTrackedPropertyRequest(BaseModel):
    property_id: UUID
    check_in: date
    check_out: date
    interval_hours: Literal[6, 12, 24, 48]


class TrackedPropertyResponse(BaseModel):
    id: UUID
    property_id: UUID
    check_in: date
    check_out: date
    interval_hours: int
    is_active: bool
    min_price_seen: Decimal | None = None
    last_successful_run_at: datetime | None = None
    next_run_at: datetime
    telegram_warning: str | None = None

    model_config = {"from_attributes": True}


class TrackedPropertyListResponse(BaseModel):
    items: list[TrackedPropertyResponse]
    total: int
