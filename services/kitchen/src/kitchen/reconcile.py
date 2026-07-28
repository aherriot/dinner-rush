"""Ticket-progression crash-safety net.

Celery's Redis-broker ETA tasks are held only in the worker process's own
memory — `advance_ticket.apply_async(countdown=...)` (`tasks.py`) schedules
the *next* cook-progression step, but if that worker process hiccups
(a prefork child respawn, a moment of contention) before the countdown
elapses, the scheduled message is gone with no trace: nothing redelivers
it, nothing errors, the ticket just stops advancing forever. Unlike
`slots.reap_stuck_slots` (a committed row is the state, so reclaiming it is
a plain UPDATE), a lost Celery message has to be *replaced* with a new one,
and that new one needs the same `sequence`/`causation_id` bookkeeping the
lost one would have carried — reconstructed here from the ticket's own
outbox history, since the event log, not Celery's queue, is this project's
actual source of truth (DECISIONS.md §0004).

Idempotent like its slot-reaping sibling: a ticket only qualifies once it's
sat in a non-terminal, post-`queued` status longer than that step's own
expected duration plus a grace window, so running this sweep against an
already-healthy kitchen changes nothing.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from kitchen.models import Ticket
from kitchen.tasks import advance_ticket, expected_step_delay_seconds

#: `queued` is excluded — `start_prep` fires synchronously inside the
#: `order.accepted` consumer's own transaction (`consumers.py`), not via a
#: countdown, so it can't be lost the way the later, Celery-scheduled steps
#: can. Value is the `STEPS` index still pending for a ticket in that status.
_NEXT_STEP_INDEX: dict[str, int] = {"prepping": 1, "baking": 2, "boxed": 3}

_LAST_OUTBOX_EVENT_SQL = text(
    """
    SELECT envelope->>'event_id' AS event_id, (envelope->>'sequence')::int AS sequence
      FROM outbox
     WHERE envelope->>'aggregate_id' = :order_id
     ORDER BY (envelope->>'sequence')::int DESC
     LIMIT 1
    """
)


@dataclass(frozen=True)
class ReconciledTicket:
    ticket_id: UUID
    code: str
    resumed_step: str


def _expected_elapsed_seconds(ticket: Ticket, through_step_index: int, speed: int) -> float:
    total = sum(expected_step_delay_seconds(ticket, i) for i in range(through_step_index + 1))
    return total / speed


def _as_utc(value: datetime) -> datetime:
    """`Ticket.queued_at` is a naive-on-disk "timestamp without time zone"
    column that this codebase only ever writes `datetime.now(UTC)` into
    (`consumers.py`) — naive-but-really-UTC. Whether a given ORM instance
    hands back the original aware value or a freshly-loaded naive one
    depends on SQLAlchemy's identity-map/expiry state, which this function
    has no business caring about; it just normalises either to aware UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def reconcile_stuck_tickets(
    session: Session, *, grace_seconds: float, speed: int
) -> list[ReconciledTicket]:
    now = datetime.now(UTC)
    reconciled: list[ReconciledTicket] = []

    candidates = (
        session.query(Ticket).filter(Ticket.status.in_(list(_NEXT_STEP_INDEX))).all()
    )
    for ticket in candidates:
        next_step_index = _NEXT_STEP_INDEX[ticket.status]
        expected = _expected_elapsed_seconds(ticket, next_step_index, speed)
        elapsed = (now - _as_utc(ticket.queued_at)).total_seconds()
        if elapsed <= expected + grace_seconds:
            continue

        last_event = session.execute(
            _LAST_OUTBOX_EVENT_SQL, {"order_id": str(ticket.order_id)}
        ).one_or_none()
        if last_event is None:
            # No event at all for this order yet (shouldn't happen — even
            # ticket creation writes `order.queued` in the same transaction)
            # — nothing to safely resume causation from, so skip rather
            # than guess a sequence number.
            continue

        advance_ticket.apply_async(
            args=(str(ticket.id), next_step_index, last_event.sequence + 1, last_event.event_id),
            countdown=0,
        )
        reconciled.append(
            ReconciledTicket(
                ticket_id=ticket.id, code=ticket.code, resumed_step=ticket.status
            )
        )

    return reconciled
