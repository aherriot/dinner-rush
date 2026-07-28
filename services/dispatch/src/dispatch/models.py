"""Dispatch's domain model (SPEC.md §1.3) and event-spine tables.

Dispatch's database is allowed to hold address text (`address_grant.line1`,
`pending_dropoff.line1`) — unlike kitchen, whose database has none, by
design. The PII boundary here is access-level (the time-boxed grant, §6.2),
not schema-level; see ADR 0007's introduction for why that distinction is
deliberate rather than an inconsistency with kitchen's rule.

`Outbox`/`ProcessedEvent` mirror the gateway's and kitchen's tables exactly
(DECISIONS.md §0004) — same shape, own database — so
`dinner_rush_core.outbox`'s cursor-based relay/idempotency helpers work
unmodified here too.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Numeric, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dinner_rush_core.ids import uuid7
from dispatch.db import Base


class Courier(Base):
    __tablename__ = "courier"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str]
    status: Mapped[str] = mapped_column(default="offline")  # offline|idle|assigned|delivering
    vehicle: Mapped[str]  # bike | scooter
    speed_cells_per_min: Mapped[float] = mapped_column(Numeric(6, 2))
    shift_started_at: Mapped[datetime | None] = mapped_column(nullable=True)

    trips: Mapped[list["Trip"]] = relationship(back_populates="courier")


class Trip(Base):
    __tablename__ = "trip"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    courier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courier.id"))
    order_id: Mapped[uuid.UUID]
    code: Mapped[str]
    # assigned | picked_up | delivering | delivered | failed | unassigned
    # (`unassigned` is ADR 0007 §4 — not in SPEC.md's original enum.)
    status: Mapped[str] = mapped_column(default="assigned")

    pickup_x: Mapped[int] = mapped_column(SmallInteger)
    pickup_y: Mapped[int] = mapped_column(SmallInteger)
    dropoff_x: Mapped[int] = mapped_column(SmallInteger)
    dropoff_y: Mapped[int] = mapped_column(SmallInteger)

    assigned_at: Mapped[datetime]
    picked_up_at: Mapped[datetime | None] = mapped_column(nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    eta_at: Mapped[datetime]
    distance_cells: Mapped[int]
    failure_reason: Mapped[str | None] = mapped_column(nullable=True)

    courier: Mapped["Courier"] = relationship(back_populates="trips")
    grants: Mapped[list["AddressGrant"]] = relationship(back_populates="trip")


class AddressGrant(Base):
    """The time-boxed permission from PIZZA.md, made real (SPEC.md §6.2)."""

    __tablename__ = "address_grant"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trip.id"))
    courier_id: Mapped[uuid.UUID]
    dropoff_x: Mapped[int] = mapped_column(SmallInteger)
    dropoff_y: Mapped[int] = mapped_column(SmallInteger)
    line1: Mapped[str]
    granted_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)

    trip: Mapped["Trip"] = relationship(back_populates="grants")


class PendingDropoff(Base):
    """Bridges `order.placed` (which carries the address, ADR 0007 §1) to
    whenever `order.ready` arrives later for the same order — durable, so a
    `docker compose stop dispatch` mid-flight loses nothing."""

    __tablename__ = "pending_dropoff"

    order_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    code: Mapped[str]
    dropoff_x: Mapped[int] = mapped_column(SmallInteger)
    dropoff_y: Mapped[int] = mapped_column(SmallInteger)
    line1: Mapped[str]
    created_at: Mapped[datetime]


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
