"""The fake, instant cooking pipeline (PHASES.md Phase 2).

An accepted order needs to visibly progress to `delivered` for the demo, but
there is no kitchen, no Celery, and no event spine yet — those are Phases 3
and 4. This stands in with a plain background thread that walks the order
through the FSM on fixed short delays, writing `OrderStatusEvent` rows so the
tracker has something to poll. It is explicitly a placeholder: Phase 3
replaces it with Celery-scheduled tasks driven by real cook times, publishing
through the outbox instead of writing directly to this table. See ADR 0002.

Delays are domain seconds, divided by SPEED at the point of use — the
no-virtual-clock rule (SPEC.md §5) applies even to a stand-in.
"""

import threading
import time

from django.db import transaction
from django.utils import timezone

from gateway.accounts.speed import get_speed
from gateway.orders.fsm import apply_transition, is_terminal
from gateway.orders.models import Order, OrderStatusEvent

# (event, domain-seconds-of-delay-before-firing-it)
STEPS: list[tuple[str, int]] = [
    ("enqueue", 2),
    ("start_prep", 3),
    ("start_bake", 3),
    ("finish_bake", 4),
    ("mark_ready", 1),
    ("assign", 2),
    ("pick_up", 2),
    ("depart", 1),
    ("deliver", 3),
]


def _run(order_id: str) -> None:
    # Django connections are thread-local — a freshly started thread lazily
    # opens its own on first query, so there's nothing to clean up on entry.
    for event, delay_seconds in STEPS:
        time.sleep(delay_seconds / get_speed())

        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            if is_terminal(order.status):
                return

            from_status = order.status
            to_status = apply_transition(from_status, event)
            order.status = to_status
            now = timezone.now()
            if to_status == "ready":
                order.ready_at = now
            if to_status == "delivered":
                order.delivered_at = now
            order.save()

            OrderStatusEvent.objects.create(
                order=order, from_status=from_status, to_status=to_status, event=event
            )


def start_fake_progression(order_id: str) -> None:
    threading.Thread(target=_run, args=(order_id,), daemon=True).start()
