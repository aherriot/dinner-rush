"""Oven-slot allocation (DECISIONS.md §0002).

Postgres is the authority; there is no lease. The claim **is** the state —
a committed row, not a timed promise about one. `SKIP LOCKED` lets
concurrent claimers skip past each other's locked rows onto different slots
instead of serialising into a queue, so it's fast under contention, not
merely correct. Zero rows returned means the kitchen is at capacity; this
module only claims — the caller decides what that means (retry, requeue,
reject).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

_CLAIM_SQL = text(
    """
    UPDATE oven_slot
       SET order_id = :order_id,
           claimed_at = now(),
           frees_at = now() + (:cook_duration_seconds * interval '1 second')
     WHERE id = (
        SELECT s.id
          FROM oven_slot s
          JOIN oven o ON o.id = s.oven_id
         WHERE s.order_id IS NULL
           AND o.status = 'available'
         ORDER BY s.oven_id, s.slot_index
           FOR UPDATE OF s SKIP LOCKED
         LIMIT 1
     )
    RETURNING id, oven_id, slot_index, frees_at
    """
)

_RELEASE_SQL = text(
    """
    UPDATE oven_slot
       SET order_id = NULL, claimed_at = NULL, frees_at = NULL
     WHERE id = :oven_slot_id
    RETURNING id, oven_id, slot_index
    """
)

_REAP_SQL = text(
    """
    UPDATE oven_slot
       SET order_id = NULL, claimed_at = NULL, frees_at = NULL
     WHERE frees_at < now() - (:grace_seconds * interval '1 second')
    RETURNING id, oven_id, slot_index
    """
)

_COUNT_OCCUPIED_SQL = text("SELECT count(*) FROM oven_slot WHERE order_id IS NOT NULL")


@dataclass(frozen=True)
class ClaimedSlot:
    oven_slot_id: uuid.UUID
    oven_id: uuid.UUID
    slot_index: int
    frees_at: datetime


@dataclass(frozen=True)
class FreedSlot:
    oven_slot_id: uuid.UUID
    oven_id: uuid.UUID
    slot_index: int


def claim_slot(
    session: Session, order_id: uuid.UUID, cook_duration_seconds: float
) -> ClaimedSlot | None:
    row = session.execute(
        _CLAIM_SQL, {"order_id": str(order_id), "cook_duration_seconds": cook_duration_seconds}
    ).one_or_none()
    if row is None:
        return None
    return ClaimedSlot(
        oven_slot_id=row.id, oven_id=row.oven_id, slot_index=row.slot_index, frees_at=row.frees_at
    )


def release_slot(session: Session, oven_slot_id: uuid.UUID) -> FreedSlot:
    row = session.execute(_RELEASE_SQL, {"oven_slot_id": str(oven_slot_id)}).one()
    return FreedSlot(oven_slot_id=row.id, oven_id=row.oven_id, slot_index=row.slot_index)


def reap_stuck_slots(session: Session, grace_seconds: float) -> list[FreedSlot]:
    """Idempotent — running it twice changes nothing. The crash-safety net:
    if the kitchen process dies mid-bake, the row still reads occupied until
    this sweep reclaims it, well past when the bake should have finished."""
    rows = session.execute(_REAP_SQL, {"grace_seconds": grace_seconds}).all()
    return [
        FreedSlot(oven_slot_id=row.id, oven_id=row.oven_id, slot_index=row.slot_index)
        for row in rows
    ]


def count_occupied_slots(session: Session) -> int:
    return int(session.execute(_COUNT_OCCUPIED_SQL).scalar_one())
