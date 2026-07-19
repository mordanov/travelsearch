from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class CreateTrackedSearchRequest(BaseModel):
    search_id: UUID
    interval_hours: Literal[6, 12, 24, 48]


class TrackedSearchResponse(BaseModel):
    id: UUID
    search_id: UUID
    destination: str
    check_in: datetime
    check_out: datetime
    interval_hours: int
    is_active: bool
    last_successful_run_at: datetime | None = None
    next_run_at: datetime
    telegram_warning: str | None = None

    model_config = {"from_attributes": True}


class TrackedSearchListResponse(BaseModel):
    items: list[TrackedSearchResponse]
    total: int
