"""Consumer group handlers, keyed by group name (SPEC.md §4 classification).

Three groups now:

- `cg:analytics` writes to Postgres and must be effectively-once, so it
  dedupes via `processed_event` in the same transaction as its side effect
  (an `EventTypeCounter` increment — small enough to write a clean
  redelivery-is-a-no-op test against).
- `cg:ws-fanout` pushes to an in-memory Channels group and is at-least-once
  by design; the browser dedupes by `event_id` client-side, so there is
  nothing to make idempotent server-side. It's also the one handler that
  needs the Redis stream id (not just the envelope) — see its own
  docstring — so it's the one entry in `HANDLERS` that takes a
  `StreamMessage` directly instead of a bare `EventEnvelope`.
- `cg:order-sync` (Phase 4) folds kitchen's own `order.queued`/`baking`/
  `baked`/`ready` events back into this `Order`'s `status` and timeline —
  gateway no longer drives those transitions itself, kitchen does, and this
  is how the REST/timeline/websocket surfaces still see them.
"""

from collections.abc import Callable

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection, transaction
from django.utils import timezone

from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.outbox import mark_processed_or_skip
from dinner_rush_core.streams import StreamMessage
from gateway.eventing.models import EventTypeCounter
from gateway.orders.fsm import is_terminal
from gateway.orders.models import Order, OrderStatusEvent

CONSUMER_GROUP_ANALYTICS = "cg:analytics"
CONSUMER_GROUP_WS_FANOUT = "cg:ws-fanout"
CONSUMER_GROUP_ORDER_SYNC = "cg:order-sync"

# Kitchen's event types map onto the FSM event name (for the timeline) and
# the resulting status. This sets `status` directly rather than routing
# through `fsm.apply_transition` — kitchen already validated the transition
# before firing the event, and its own `queued -> prepping` step
# (`start_prep`) has no catalogue event (SPEC.md §4), so gateway's mirror of
# `status` intentionally coarsens `prepping` into `queued` until the next
# event it actually hears about arrives. `apply_transition`'s strict
# single-hop table is for transitions gateway itself still drives (place,
# accept, reject) — this handler trusts kitchen's, not re-derives them.
_EVENT_TYPE_TO_TRANSITION = {
    "order.queued": ("enqueue", "queued"),
    "order.baking": ("start_bake", "baking"),
    "order.baked": ("finish_bake", "boxed"),
    "order.ready": ("mark_ready", "ready"),
}


def handle_analytics(envelope: EventEnvelope) -> None:
    with transaction.atomic():
        should_process = mark_processed_or_skip(
            connection.cursor(), CONSUMER_GROUP_ANALYTICS, envelope.event_id
        )
        if not should_process:
            return
        counter, _ = EventTypeCounter.objects.select_for_update().get_or_create(
            event_type=envelope.event_type
        )
        counter.count += 1
        counter.save(update_fields=["count"])


def handle_ws_fanout(message: StreamMessage) -> None:
    """Needs `message.message_id` — the actual Redis stream id — alongside
    the envelope, because the browser echoes it back as `?last_event_id=`
    on reconnect (DECISIONS.md §0003: "resumes from a last-seen event id"),
    and only a genuine stream id (`<ms>-<seq>`) is valid there; the
    envelope's own `event_id` is a business UUID and `XRANGE` rejects it
    outright. Send both, under different names, so the browser never
    confuses the two."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"order.{message.envelope.aggregate_id}",
        {
            "type": "order.event",
            "envelope": message.envelope.model_dump(mode="json"),
            "stream_id": message.message_id,
        },
    )


def handle_order_sync(envelope: EventEnvelope) -> None:
    transition = _EVENT_TYPE_TO_TRANSITION.get(envelope.event_type)
    if transition is None:
        return
    fsm_event, to_status = transition

    with transaction.atomic():
        should_process = mark_processed_or_skip(
            connection.cursor(), CONSUMER_GROUP_ORDER_SYNC, envelope.event_id
        )
        if not should_process:
            return
        order = Order.objects.select_for_update().get(id=envelope.aggregate_id)
        if is_terminal(order.status):
            return
        from_status = order.status
        order.status = to_status
        if to_status == "ready":
            order.ready_at = timezone.now()
        order.save()
        OrderStatusEvent.objects.create(
            order=order, from_status=from_status, to_status=to_status, event=fsm_event
        )

    if to_status == "ready":
        from gateway.orders.tasks import start_dispatch_progression

        start_dispatch_progression(
            order, sequence=envelope.sequence + 1, causation_id=str(envelope.event_id)
        )


HANDLERS: dict[str, Callable[[StreamMessage], None]] = {
    CONSUMER_GROUP_ANALYTICS: lambda message: handle_analytics(message.envelope),
    CONSUMER_GROUP_WS_FANOUT: handle_ws_fanout,
    CONSUMER_GROUP_ORDER_SYNC: lambda message: handle_order_sync(message.envelope),
}
