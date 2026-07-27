"""Celery-scheduled dispatch stand-in (PHASES.md Phase 4).

Kitchen now owns `enqueue` through `mark_ready` (SPEC.md §2) — it consumes
`order.accepted` itself and publishes `order.queued`/`order.baking`/
`order.baked`/`order.ready`, which `gateway.eventing.handlers.handle_order_sync`
folds back into this `Order`'s own `status` and timeline. This module picks
up from there: `order.ready` kicks off `assign -> pick_up -> depart ->
deliver`, still faked with fixed delays because dispatch doesn't exist
until Phase 7. Every transition still writes its `OrderStatusEvent` and,
where the catalogue has a matching event type, its outbox row, in the same
transaction as the state change (DECISIONS.md §0004).
"""

from dataclasses import dataclass
from uuid import UUID

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from gateway.accounts.speed import get_speed
from gateway.eventing.writer import build_envelope, write_outbox_event
from gateway.orders.fsm import apply_transition, is_terminal
from gateway.orders.models import Order, OrderStatusEvent


@dataclass(frozen=True)
class Step:
    event: str
    event_type: str | None  # None where the catalogue has no matching event yet


STEPS: list[Step] = [
    Step("assign", None),
    Step("pick_up", None),
    Step("depart", None),
    Step("deliver", "order.delivered"),
]

# Domain-second delay *before* each step fires, indexed the same as STEPS —
# all fixed, since there's no real courier to time against yet.
_FIXED_DELAYS: list[int] = [2, 2, 1, 3]


def _payload(order: Order, event_type: str) -> dict[str, object]:
    now = timezone.now()
    if event_type == "order.delivered":
        elapsed = (now - order.placed_at).total_seconds()
        return {"code": order.code, "courier_id": "sim-courier-1", "total_elapsed_s": elapsed}
    raise AssertionError(f"no payload rule for event type {event_type!r}")


@shared_task(name="orders.advance")
def advance_order(
    order_id: str, step_index: int, sequence: int, causation_id: str | None
) -> None:
    with transaction.atomic():
        order = Order.objects.select_for_update().get(id=order_id)
        if is_terminal(order.status):
            return

        step = STEPS[step_index]
        from_status = order.status
        to_status = apply_transition(from_status, step.event)
        order.status = to_status
        if to_status == "delivered":
            order.delivered_at = timezone.now()
        order.save()

        OrderStatusEvent.objects.create(
            order=order, from_status=from_status, to_status=to_status, event=step.event
        )

        next_causation_id = causation_id
        next_sequence = sequence
        if step.event_type is not None:
            envelope = build_envelope(
                event_type=step.event_type,
                aggregate_type="order",
                aggregate_id=order.id,
                sequence=sequence,
                correlation_id=order.id,
                causation_id=UUID(causation_id) if causation_id else None,
                payload=_payload(order, step.event_type),
            )
            write_outbox_event(envelope)
            next_causation_id = str(envelope.event_id)
            next_sequence = sequence + 1

    if step_index + 1 < len(STEPS):
        delay = _FIXED_DELAYS[step_index + 1] / get_speed()
        advance_order.apply_async(
            args=(order_id, step_index + 1, next_sequence, next_causation_id),
            countdown=delay,
        )


def start_dispatch_progression(order: Order, *, sequence: int, causation_id: str) -> None:
    """Kick off `assign` right after `order.ready` is folded into this
    `Order` (`handlers.handle_order_sync`)."""
    delay = _FIXED_DELAYS[0] / get_speed()
    advance_order.apply_async(args=(str(order.id), 0, sequence, causation_id), countdown=delay)
