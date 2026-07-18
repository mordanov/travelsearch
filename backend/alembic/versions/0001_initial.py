"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.Text, nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger, nullable=True),
        sa.Column("telegram_linked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("telegram_chat_id"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # properties
    op.create_table(
        "properties",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_property_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("location", sa.Text, nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("bedrooms", sa.SmallInteger, nullable=True),
        sa.Column("bathrooms", sa.SmallInteger, nullable=True),
        sa.Column("amenities", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_property_id", name="uq_property_identity"),
    )

    # searches
    op.create_table(
        "searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("destination", sa.Text, nullable=False),
        sa.Column("check_in", sa.DateTime(timezone=False), nullable=False),
        sa.Column("check_out", sa.DateTime(timezone=False), nullable=False),
        sa.Column("guests", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("providers", postgresql.ARRAY(sa.String(50)), nullable=False),
        sa.Column("filters", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("provider_statuses", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_searches_user_id", "searches", ["user_id"])

    # search_results
    op.create_table(
        "search_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("search_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price_per_night", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("distance_km", sa.Numeric(6, 2), nullable=True),
        sa.Column("free_cancellation", sa.Boolean, nullable=True),
        sa.Column("raw_snapshot", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["search_id"], ["searches.id"]),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_results_search_id", "search_results", ["search_id"])

    # tracked_searches
    op.create_table(
        "tracked_searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("search_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interval_hours", sa.SmallInteger, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_successful_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("interval_hours IN (6, 12, 24, 48)", name="ck_tracked_search_interval"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["search_id"], ["searches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "search_id", name="uq_tracked_search"),
    )
    op.create_index("ix_tracked_search_active_next_run", "tracked_searches", ["is_active", "next_run_at"])
    op.create_index("ix_tracked_searches_user_id", "tracked_searches", ["user_id"])

    # tracked_search_seen_properties
    op.create_table(
        "tracked_search_seen_properties",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tracked_search_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("min_price_seen", sa.Numeric(10, 2), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tracked_search_id"], ["tracked_searches.id"]),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tracked_search_id", "property_id", name="uq_tracked_search_seen_property"),
    )
    op.create_index("ix_seen_property_tracked_search", "tracked_search_seen_properties", ["tracked_search_id"])

    # tracked_properties
    op.create_table(
        "tracked_properties",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("check_in", sa.DateTime(timezone=False), nullable=False),
        sa.Column("check_out", sa.DateTime(timezone=False), nullable=False),
        sa.Column("interval_hours", sa.SmallInteger, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("min_price_seen", sa.Numeric(10, 2), nullable=True),
        sa.Column("last_successful_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("interval_hours IN (6, 12, 24, 48)", name="ck_tracked_property_interval"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "property_id", "check_in", "check_out", name="uq_tracked_property"),
    )
    op.create_index("ix_tracked_property_active_next_run", "tracked_properties", ["is_active", "next_run_at"])
    op.create_index("ix_tracked_property_user_checkin", "tracked_properties", ["user_id", "check_in"])

    # notification_logs
    op.create_table(
        "notification_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="telegram"),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tracked_search_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tracked_property_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("price_before", sa.Numeric(10, 2), nullable=True),
        sa.Column("price_after", sa.Numeric(10, 2), nullable=False),
        sa.Column("property_url", sa.Text, nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("delivery_status", sa.String(20), nullable=False, server_default="sent"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.ForeignKeyConstraint(["tracked_search_id"], ["tracked_searches.id"]),
        sa.ForeignKeyConstraint(["tracked_property_id"], ["tracked_properties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_log_user_sent", "notification_logs", ["user_id", "sent_at"])
    op.create_index("ix_notification_log_property", "notification_logs", ["property_id"])

    # price_snapshots
    op.create_table(
        "price_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("check_in", sa.DateTime(timezone=False), nullable=False),
        sa.Column("check_out", sa.DateTime(timezone=False), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_snapshots_property_id", "price_snapshots", ["property_id"])


def downgrade() -> None:
    op.drop_table("price_snapshots")
    op.drop_table("notification_logs")
    op.drop_table("tracked_properties")
    op.drop_table("tracked_search_seen_properties")
    op.drop_table("tracked_searches")
    op.drop_table("search_results")
    op.drop_table("searches")
    op.drop_table("properties")
    op.drop_table("users")
