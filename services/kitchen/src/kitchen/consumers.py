"""`cg:kitchen` — builds tickets from `order.accepted` events (SPEC.md §1.2).

Kitchen never reads the gateway's `order` table; this is the only way a
ticket comes into existence, and it's also the PII boundary — only `code`
and item skus/qty cross in, because that's all `order.accepted`'s payload
carries.

`events:order` carries every order event, not just this one (one stream per
aggregate, not per event type — DECISIONS.md §0003), so this handler checks
`envelope.event_type` itself rather than relying on `HANDLERS` to route by
type, same as `dispatch.consumers.handle_order_stream` and
`gateway.eventing.handlers.handle_order_sync`.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dinner_rush_core.config import load_config
from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.outbox import mark_processed_or_skip
from kitchen.dbapi import raw_cursor
from kitchen.models import Ticket
from kitchen.tasks import start_progression
from kitchen.writer import build_envelope, write_outbox_event

CONSUMER_GROUP = "cg:kitchen"


def _queue_depth_ahead_of(session: Session, ticket_id: object) -> int:
    stmt = (
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.status != "ready", Ticket.id != ticket_id)
    )
    return int(session.execute(stmt).scalar_one())


def _bake_seconds(items: list[dict[str, object]]) -> int:
    """Items bake together in the oven — the slowest one sets the ticket's
    total bake time, not the sum (Phase 4 simplification: one ticket claims
    exactly one slot regardless of `menu_item.oven_slots`; multi-slot claims
    for party-size items are a follow-on, noted in ADR 0004)."""
    menu_by_sku = {item.sku: item for item in load_config().menu}
    return max(menu_by_sku[str(line["sku"])].bake_seconds for line in items)


def handle_order_accepted(session: Session, envelope: EventEnvelope) -> None:
    if envelope.event_type != "order.accepted":
        return

    should_process = mark_processed_or_skip(raw_cursor(session), CONSUMER_GROUP, envelope.event_id)
    if not should_process:
        return

    items = envelope.payload["items"]
    assert isinstance(items, list)
    ticket = Ticket(
        order_id=envelope.aggregate_id,
        code=str(envelope.payload["code"]),
        status="queued",
        items=items,
        total_bake_seconds=_bake_seconds(items),
        queued_at=datetime.now(UTC),
    )
    session.add(ticket)
    session.flush()

    queued_envelope = build_envelope(
        event_type="order.queued",
        aggregate_type="order",
        aggregate_id=ticket.order_id,
        sequence=envelope.sequence + 1,
        correlation_id=ticket.order_id,
        causation_id=envelope.event_id,
        payload={
            "code": ticket.code,
            "position": _queue_depth_ahead_of(session, ticket.id) + 1,
            "projected_start_at": datetime.now(UTC),
        },
    )
    write_outbox_event(session, queued_envelope)
    session.commit()

    start_progression(
        ticket, sequence=envelope.sequence + 2, causation_id=str(queued_envelope.event_id)
    )


HANDLERS = {CONSUMER_GROUP: handle_order_accepted}
