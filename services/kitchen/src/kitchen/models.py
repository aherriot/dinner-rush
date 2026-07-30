"""Kitchen's domain model (SPEC.md §1.2) and event-spine tables.

Kitchen never reads front-of-house's `order` table — tickets are built from
`order.accepted` events only (`consumers.py`), and this database holds no
customer PII: `Ticket` carries `code` and item snapshots, nothing else.
Separate Postgres database, no shared connection string (CLAUDE.md §3/§5).

`Outbox`/`ProcessedEvent` mirror front-of-house's tables exactly (DECISIONS.md
§0004) — same shape, own database — so `dinner_rush_core.outbox`'s
cursor-based relay/idempotency helpers work unmodified against either.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    SmallInteger,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dinner_rush_core.ids import uuid7
from kitchen.db import Base


class Oven(Base):
    __tablename__ = "oven"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str]
    slot_count: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(default="available")  # available | down
    #: Per-aggregate monotonic counter for this oven's own `oven.down`/
    #: `oven.restored` chain (EventEnvelope.sequence, DECISIONS.md §0004) —
    #: unlike order/ticket events, an oven has no upstream causation chain to
    #: thread a sequence through, so it keeps its own running count.
    event_sequence: Mapped[int] = mapped_column(default=0)

    slots: Mapped[list["OvenSlot"]] = relationship(
        back_populates="oven", order_by="OvenSlot.slot_index"
    )


class OvenSlot(Base):
    __tablename__ = "oven_slot"
    __table_args__ = (
        UniqueConstraint("oven_id", "slot_index", name="uq_oven_slot_index"),
        # The second line of defence against double-booking (DECISIONS.md
        # §0002) — even an application bug cannot put one order in two
        # slots, because the database refuses the second row.
        Index(
            "one_slot_per_order",
            "order_id",
            unique=True,
            postgresql_where=text("order_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    oven_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("oven.id"))
    slot_index: Mapped[int] = mapped_column(SmallInteger)
    order_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    frees_at: Mapped[datetime | None] = mapped_column(nullable=True)

    oven: Mapped["Oven"] = relationship(back_populates="slots")


class Station(Base):
    __tablename__ = "station"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str]
    kind: Mapped[str]  # prep | assembly
    capacity: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(default="available")


class Ticket(Base):
    __tablename__ = "ticket"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    order_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    code: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    items: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    total_bake_seconds: Mapped[int]
    queued_at: Mapped[datetime]
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    baked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(nullable=True)
    oven_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("oven_slot.id"), nullable=True
    )
    priority: Mapped[int] = mapped_column(default=0)


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    stream: Mapped[str]
    envelope: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime]
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ProcessedEvent(Base):
    __tablename__ = "processed_event"
    __table_args__ = (UniqueConstraint("consumer_group", "event_id", name="processed_event_dedup"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    consumer_group: Mapped[str]
    event_id: Mapped[uuid.UUID]
    processed_at: Mapped[datetime]
