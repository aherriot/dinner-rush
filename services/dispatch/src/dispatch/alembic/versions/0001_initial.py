"""initial dispatch schema

Revision ID: 0001
Revises:
Create Date: 2026-07-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "courier",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="offline"),
        sa.Column("vehicle", sa.String(), nullable=False),
        sa.Column("speed_cells_per_min", sa.Numeric(6, 2), nullable=False),
        sa.Column("shift_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "trip",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("courier_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="assigned"),
        sa.Column("pickup_x", sa.SmallInteger(), nullable=False),
        sa.Column("pickup_y", sa.SmallInteger(), nullable=False),
        sa.Column("dropoff_x", sa.SmallInteger(), nullable=False),
        sa.Column("dropoff_y", sa.SmallInteger(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eta_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("distance_cells", sa.Integer(), nullable=False),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["courier_id"], ["courier.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trip_order_id", "trip", ["order_id"])
    op.create_index("ix_trip_courier_id_status", "trip", ["courier_id", "status"])

    op.create_table(
        "address_grant",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("courier_id", sa.Uuid(), nullable=False),
        sa.Column("dropoff_x", sa.SmallInteger(), nullable=False),
        sa.Column("dropoff_y", sa.SmallInteger(), nullable=False),
        sa.Column("line1", sa.String(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["trip_id"], ["trip.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_address_grant_trip_id", "address_grant", ["trip_id"])

    op.create_table(
        "pending_dropoff",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("dropoff_x", sa.SmallInteger(), nullable=False),
        sa.Column("dropoff_y", sa.SmallInteger(), nullable=False),
        sa.Column("line1", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("order_id"),
    )

    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("stream", sa.String(), nullable=False),
        sa.Column("envelope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        "outbox_unpublished",
        "outbox",
        ["id"],
        unique=False,
        postgresql_where=sa.text("published_at IS NULL"),
    )

    op.create_table(
        "processed_event",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("consumer_group", sa.String(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("consumer_group", "event_id", name="processed_event_dedup"),
    )


def downgrade() -> None:
    op.drop_table("processed_event")
    op.drop_table("outbox")
    op.drop_table("pending_dropoff")
    op.drop_index("ix_address_grant_trip_id", table_name="address_grant")
    op.drop_table("address_grant")
    op.drop_index("ix_trip_courier_id_status", table_name="trip")
    op.drop_index("ix_trip_order_id", table_name="trip")
    op.drop_table("trip")
    op.drop_table("courier")
