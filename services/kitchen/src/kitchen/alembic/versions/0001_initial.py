"""initial kitchen schema

Revision ID: 0001
Revises:
Create Date: 2026-07-27

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
        "oven",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slot_count", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="available"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "oven_slot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("oven_id", sa.Uuid(), nullable=False),
        sa.Column("slot_index", sa.SmallInteger(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("frees_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["oven_id"], ["oven.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("oven_id", "slot_index", name="uq_oven_slot_index"),
    )
    op.create_index(
        "one_slot_per_order",
        "oven_slot",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("order_id IS NOT NULL"),
    )

    op.create_table(
        "station",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("capacity", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="available"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ticket",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("total_bake_seconds", sa.Integer(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("baked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("oven_slot_id", sa.Uuid(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["oven_slot_id"], ["oven_slot.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
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
    op.drop_table("ticket")
    op.drop_table("station")
    op.drop_index("one_slot_per_order", table_name="oven_slot")
    op.drop_table("oven_slot")
    op.drop_table("oven")
