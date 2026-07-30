"""`POST /capacity/quote` (SPEC.md §3.3) — a read-only projection, never a
reservation. The gap between this quote and the real claim later (when the
ticket actually reaches `start_bake`) is why `rejected` can still occur
after a positive quote — the claim is the only thing that's authoritative.

SPEC.md's response shape also lists `promised_at`, but §5's formula
(`promised_at = accepted_at + projected_wait_s + drive_estimate_s +
buffer_s`) needs `accepted_at`, which doesn't exist yet at quote time —
front-of-house computes `promised_at` itself from this response's
`projected_wait_s`, not the other way around. Documented as a deliberate
deviation in ADR 0004.
"""

import math
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dinner_rush_core.config import CapacityConfig, MenuItemConfig
from kitchen.models import Oven, Ticket
from kitchen.slots import count_occupied_slots

_QUEUED_OR_PREPPING = ("queued", "prepping")
_NOT_READY = ("queued", "prepping", "baking", "boxed")


@dataclass(frozen=True)
class CapacityQuote:
    can_accept: bool
    queue_depth: int
    projected_wait_s: float


def quote(
    session: Session,
    *,
    items: list[tuple[str, int]],
    menu_by_sku: dict[str, MenuItemConfig],
    capacity: CapacityConfig,
) -> CapacityQuote:
    queue_depth = session.execute(
        select(func.count()).select_from(Ticket).where(Ticket.status.in_(_NOT_READY))
    ).scalar_one()

    total_slots = session.execute(
        select(func.coalesce(func.sum(Oven.slot_count), 0)).where(Oven.status == "available")
    ).scalar_one()
    any_oven_available = session.execute(
        select(func.count()).select_from(Oven).where(Oven.status == "available")
    ).scalar_one() > 0

    own_prep_seconds = sum(menu_by_sku[sku].prep_seconds for sku, _qty in items)
    own_bake_seconds = max((menu_by_sku[sku].bake_seconds for sku, _qty in items), default=0)
    avg_bake_seconds = _average_bake_seconds(session, default=own_bake_seconds)

    queued_ahead = session.execute(
        select(func.count()).select_from(Ticket).where(Ticket.status.in_(_QUEUED_OR_PREPPING))
    ).scalar_one()
    occupied = count_occupied_slots(session)
    free_slots_now = max(total_slots - occupied, 0)

    if free_slots_now > 0 and queued_ahead == 0:
        projected_wait_s = float(own_prep_seconds)
    else:
        batches_ahead = math.ceil((queued_ahead + 1) / max(total_slots, 1))
        projected_wait_s = own_prep_seconds + batches_ahead * avg_bake_seconds

    can_accept = True
    if capacity.reject_when_all_ovens_down and not any_oven_available:
        can_accept = False
    if queue_depth >= capacity.max_queue_depth:
        can_accept = False
    if projected_wait_s > capacity.max_projected_wait_seconds:
        can_accept = False

    return CapacityQuote(
        can_accept=can_accept, queue_depth=queue_depth, projected_wait_s=projected_wait_s
    )


def _average_bake_seconds(session: Session, *, default: int) -> float:
    avg = session.execute(select(func.avg(Ticket.total_bake_seconds))).scalar_one()
    return float(avg) if avg is not None else float(default)
