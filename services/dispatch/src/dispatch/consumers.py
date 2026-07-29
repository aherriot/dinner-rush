"""`cg:dispatch` — subscribed to `events:order` like every other group, but
reacts to two event types (ADR 0007 §1, §2):

- `order.placed` — the only place the dropoff address exists on the wire.
  Cached into `pending_dropoff`, keyed by `order_id`, so it's on hand
  whenever `order.ready` shows up later for the same order — which may be a
  long time later, and across a dispatch restart.
- `order.ready` — the actual assignment trigger. Looks up the cached
  dropoff, tries once to match a courier (`dispatch.assignment`), and hands
  off to `dispatch.tasks` to retry on a timer if none is free yet.

Every other event type on this stream (`order.accepted`, `order.baking`, …)
is silently ignored — each handler below checks `envelope.event_type` itself
rather than relying on `HANDLERS` to route by type, same as
`gateway.eventing.handlers.handle_order_sync`.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.outbox import mark_processed_or_skip
from dispatch.dbapi import raw_cursor
from dispatch.models import PendingDropoff
from dispatch.tasks import try_assign

CONSUMER_GROUP = "cg:dispatch"


def handle_order_stream(session: Session, envelope: EventEnvelope) -> None:
    if envelope.event_type not in ("order.placed", "order.ready"):
        return

    should_process = mark_processed_or_skip(raw_cursor(session), CONSUMER_GROUP, envelope.event_id)
    if not should_process:
        return

    if envelope.event_type == "order.placed":
        _cache_dropoff(session, envelope)
    else:
        _trigger_assignment(session, envelope)
    session.commit()


def _cache_dropoff(session: Session, envelope: EventEnvelope) -> None:
    session.add(
        PendingDropoff(
            order_id=envelope.aggregate_id,
            code=str(envelope.payload["code"]),
            dropoff_x=int(envelope.payload["grid_x"]),
            dropoff_y=int(envelope.payload["grid_y"]),
            line1=str(envelope.payload["line1"]),
            created_at=datetime.now(UTC),
        )
    )


def _trigger_assignment(session: Session, envelope: EventEnvelope) -> None:
    pending = session.get(PendingDropoff, envelope.aggregate_id)
    if pending is None:
        # order.placed hasn't been processed yet (redelivery raced ahead of
        # it, or a bug upstream) — nothing to assign against. `order.ready`
        # isn't acked by the caller in this case; XAUTOCLAIM will retry it.
        raise RuntimeError(f"no pending_dropoff for order {envelope.aggregate_id}")
    pending.ready_at = datetime.now(UTC)
    try_assign(
        order_id=pending.order_id,
        code=pending.code,
        dropoff_x=pending.dropoff_x,
        dropoff_y=pending.dropoff_y,
        line1=pending.line1,
        sequence=envelope.sequence + 1,
        causation_id=str(envelope.event_id),
    )


HANDLERS = {CONSUMER_GROUP: handle_order_stream}
