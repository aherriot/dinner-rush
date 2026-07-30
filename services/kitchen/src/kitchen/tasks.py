"""Celery-scheduled cook progression: `queued -> prepping -> baking -> boxed
-> ready` (SPEC.md §2), kitchen's slice of the FSM — the rest of what
gateway's Phase 3 stand-in used to do entirely by itself.

Real durations, scaled by `SPEED` at the point each step is scheduled
(SPEC.md §5), never stored pre-scaled. `start_bake` claims a real oven slot
(DECISIONS.md §0002); `finish_bake` releases it and publishes
`oven.slot_freed`. A claim that loses the race (kitchen at capacity right
now, even though the order was accepted earlier) retries with a short
backoff rather than failing an already-accepted order — there is no FSM
transition back out of `baking` for "couldn't get a slot".
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from celery import shared_task

from dinner_rush_core.config import load_config
from kitchen.celery_app import app  # noqa: F401 - registers this module's tasks
from kitchen.db import SessionLocal
from kitchen.fsm import apply_transition, is_terminal
from kitchen.models import Ticket
from kitchen.slots import ClaimedSlot, claim_slot, release_slot
from kitchen.speed import get_speed as _speed
from kitchen.writer import build_envelope, write_outbox_event

CLAIM_RETRY_COUNTDOWN_SECONDS = 5.0


@dataclass(frozen=True)
class Step:
    event: str
    event_type: str | None


STEPS: list[Step] = [
    Step("start_prep", None),
    Step("start_bake", "order.baking"),
    Step("finish_bake", "order.baked"),
    Step("mark_ready", "order.ready"),
]

_FIXED_DELAYS: list[float | None] = [3, None, None, 1]


def _prep_seconds(ticket: Ticket) -> int:
    menu_by_sku = {item.sku: item for item in load_config().menu}
    return sum(menu_by_sku[str(line["sku"])].prep_seconds for line in ticket.items)


def expected_step_delay_seconds(ticket: Ticket, step_index: int) -> float:
    """The un-scaled (domain-seconds) delay `advance_ticket` schedules
    before firing `STEPS[step_index]` — exposed for `reconcile.py`'s
    stuck-ticket sweep, which needs the same number to judge whether a
    ticket has overrun how long that step should have taken."""
    return _delay_seconds(ticket, step_index)


def _delay_seconds(ticket: Ticket, step_index: int) -> float:
    fixed = _FIXED_DELAYS[step_index]
    if fixed is not None:
        return fixed
    if STEPS[step_index].event == "start_bake":
        return _prep_seconds(ticket)
    if STEPS[step_index].event == "finish_bake":
        return ticket.total_bake_seconds
    raise AssertionError(STEPS[step_index].event)


@shared_task(name="kitchen.advance_ticket")
def advance_ticket(
    ticket_id: str, step_index: int, sequence: int, causation_id: str | None
) -> None:
    session = SessionLocal()
    try:
        ticket = session.get(Ticket, UUID(ticket_id))
        if ticket is None or is_terminal(ticket.status):
            return

        step = STEPS[step_index]

        if step.event == "start_bake":
            claimed = claim_slot(session, ticket.order_id, ticket.total_bake_seconds / _speed())
            if claimed is None:
                session.rollback()
                advance_ticket.apply_async(
                    args=(ticket_id, step_index, sequence, causation_id),
                    countdown=CLAIM_RETRY_COUNTDOWN_SECONDS / _speed(),
                )
                return
            ticket.oven_slot_id = claimed.oven_slot_id

        from_status = ticket.status
        to_status = apply_transition(from_status, step.event)
        ticket.status = to_status
        now = datetime.now(UTC)
        if to_status == "baking":
            ticket.started_at = now
        if to_status == "boxed":
            ticket.baked_at = now
        if to_status == "ready":
            ticket.ready_at = now

        next_causation_id = causation_id
        next_sequence = sequence
        if step.event_type is not None:
            slot_for_payload = claimed if step.event == "start_bake" else None
            envelope = build_envelope(
                event_type=step.event_type,
                aggregate_type="order",
                aggregate_id=ticket.order_id,
                sequence=sequence,
                correlation_id=ticket.order_id,
                causation_id=UUID(causation_id) if causation_id else None,
                payload=_payload(ticket, step.event_type, claimed=slot_for_payload),
            )
            write_outbox_event(session, envelope)
            next_causation_id = str(envelope.event_id)
            next_sequence = sequence + 1

        if step.event == "finish_bake" and ticket.oven_slot_id is not None:
            freed = release_slot(session, ticket.oven_slot_id)
            freed_envelope = build_envelope(
                event_type="oven.slot_freed",
                aggregate_type="oven",
                aggregate_id=freed.oven_id,
                sequence=next_sequence,
                correlation_id=ticket.order_id,
                causation_id=UUID(next_causation_id),
                payload={"oven_id": str(freed.oven_id), "slot_index": freed.slot_index},
            )
            write_outbox_event(session, freed_envelope)
            next_sequence += 1

        session.commit()
    finally:
        session.close()

    if step_index + 1 < len(STEPS):
        delay = _delay_seconds(ticket, step_index + 1) / _speed()
        advance_ticket.apply_async(
            args=(ticket_id, step_index + 1, next_sequence, next_causation_id),
            countdown=delay,
        )


def _payload(
    ticket: Ticket, event_type: str, *, claimed: ClaimedSlot | None = None
) -> dict[str, object]:
    now = datetime.now(UTC)
    if event_type == "order.baking":
        assert claimed is not None
        return {
            "code": ticket.code,
            "oven_id": str(claimed.oven_id),
            "slot_index": claimed.slot_index,
            "frees_at": claimed.frees_at,
        }
    if event_type == "order.baked":
        return {"code": ticket.code, "actual_bake_s": float(ticket.total_bake_seconds)}
    if event_type == "order.ready":
        return {"code": ticket.code, "ready_at": now}
    raise AssertionError(event_type)


def start_progression(ticket: Ticket, *, sequence: int, causation_id: str) -> None:
    """Kick off `start_prep` right after the ticket (and its `order.queued`
    event) commits."""
    delay = _FIXED_DELAYS[0] or 0
    advance_ticket.apply_async(
        args=(str(ticket.id), 0, sequence, causation_id), countdown=delay / _speed()
    )
