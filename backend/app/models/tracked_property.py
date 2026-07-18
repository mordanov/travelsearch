import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrackedProperty(Base):
    __tablename__ = "tracked_properties"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "property_id", "check_in", "check_out", name="uq_tracked_property"
        ),
        CheckConstraint("interval_hours IN (6, 12, 24, 48)", name="ck_tracked_property_interval"),
        Index("ix_tracked_property_active_next_run", "is_active", "next_run_at"),
        Index("ix_tracked_property_user_checkin", "user_id", "check_in"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False
    )
    check_in: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    check_out: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    interval_hours: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_price_seen: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    last_successful_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
