"""Celery-scheduled cook progression (PHASES.md Phase 3).

Replaces the fake instant-cooking thread (formerly `orders/progression.py`)
with real per-item prep/bake seconds, scaled by `SPEED` at the point each
step is scheduled — never stored pre-scaled (SPEC.md §5).

Kitchen and dispatch don't exist yet, so this monolith still walks an
accepted order all the way to `delivered` itself, one Celery task per FSM
transition. `start_bake`'s delay is the order's total prep time (single
assembly leg, no station contention modelled yet); `finish_bake`'s delay is
the slowest item's bake time (items share one oven, baking in parallel) —
both real numbers, not placeholders, in contrast to the small fixed delays
used for legs dispatch will eventually own (`assign`, `pick_up`, `depart`).
Real oven *contention* — the interesting part — is Phase 4.

Every transition writes its `OrderStatusEvent` and, where the catalogue
defines a matching event type, its outbox row, in the same transaction as
the state change (DECISIONS.md §0004). `causation_id` threads from each
step's envelope to the next so the whole chain is reconstructable from
`correlation_id` (the order's own id) alone.
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
    Step("enqueue", "order.queued"),
    Step("start_prep", None),
    Step("start_bake", "order.baking"),
    Step("finish_bake", "order.baked"),
    Step("mark_ready", "order.ready"),
    Step("assign", None),
    Step("pick_up", None),
    Step("depart", None),
    Step("deliver", "order.delivered"),
]

# Domain-second delay *before* each step fires, indexed the same as STEPS.
# `None` means "derive it from the order's own items" (see `_delay_seconds`).
_FIXED_DELAYS: list[int | None] = [2, 3, None, None, 1, 2, 2, 1, 3]


def _delay_seconds(order: Order, step_index: int) -> int:
    fixed = _FIXED_DELAYS[step_index]
    if fixed is not None:
        return fixed
    items = list(order.items.all())
    step = STEPS[step_index]
    if step.event == "start_bake":
        return sum(item.prep_seconds_snapshot for item in items)
    if step.event == "finish_bake":
        return max(item.bake_seconds_snapshot for item in items)
    raise AssertionError(f"no duration rule for step {step.event!r}")


def _payload(order: Order, event_type: str) -> dict[str, object]:
    now = timezone.now()
    if event_type == "order.queued":
        return {"code": order.code, "position": 1, "projected_start_at": now}
    if event_type == "order.baking":
        return {"code": order.code, "oven_id": "sim-oven-1", "slot_index": 0, "frees_at": now}
    if event_type == "order.baked":
        return {"code": order.code, "actual_bake_s": max(
            item.bake_seconds_snapshot for item in order.items.all()
        ) / get_speed()}
    if event_type == "order.ready":
        return {
            "code": order.code,
            "grid_x": order.address.grid_x,
            "grid_y": order.address.grid_y,
            "ready_at": now,
        }
    if event_type == "order.delivered":
        elapsed = (now - order.placed_at).total_seconds()
        return {"code": order.code, "courier_id": "sim-courier-1", "total_elapsed_s": elapsed}
    raise AssertionError(f"no payload rule for event type {event_type!r}")


@shared_task(name="orders.advance")
def advance_order(
    order_id: str, step_index: int, sequence: int, causation_id: str | None
) -> None:
    with transaction.atomic():
        order = Order.objects.select_for_update().prefetch_related("items").get(id=order_id)
        if is_terminal(order.status):
            return

        step = STEPS[step_index]
        from_status = order.status
        to_status = apply_transition(from_status, step.event)
        order.status = to_status
        if to_status == "ready":
            order.ready_at = timezone.now()
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
        delay = _delay_seconds(order, step_index + 1) / get_speed()
        advance_order.apply_async(
            args=(order_id, step_index + 1, next_sequence, next_causation_id),
            countdown=delay,
        )


def start_progression(order: Order, *, sequence: int, causation_id: str) -> None:
    """Kick off the chain right after `order.accepted` commits."""
    delay = _delay_seconds(order, 0) / get_speed()
    advance_order.apply_async(args=(str(order.id), 0, sequence, causation_id), countdown=delay)
