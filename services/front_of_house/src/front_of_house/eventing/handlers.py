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
- `cg:order-sync` (Phase 4, extended Phase 7) folds kitchen's own
  `order.queued`/`baking`/`baked`/`ready` events, and now dispatch's
  `courier.assigned`/`order.picked_up`/`order.delivering`/`order.delivered`/
  `order.failed`/`order.unassigned`, back into this `Order`'s `status` and
  timeline — front-of-house no longer drives any of those transitions itself,
  kitchen and dispatch do, and this is how the REST/timeline/websocket
  surfaces still see them. The two services publish on different streams
  (`events:order`, `events:courier` — ADR 0007 §4), so this same group name
  runs as two consumer processes, one per stream; both call this module's
  `handle_order_sync` either way.
"""

from collections.abc import Callable

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection, transaction
from django.utils import timezone

from dinner_rush_core.events.catalogue import stream_for
from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.outbox import mark_processed_or_skip
from dinner_rush_core.streams import StreamMessage
from front_of_house.eventing.models import EventTypeCounter
from front_of_house.orders.fsm import is_terminal
from front_of_house.orders.models import Order, OrderStatusEvent

CONSUMER_GROUP_ANALYTICS = "cg:analytics"
CONSUMER_GROUP_WS_FANOUT = "cg:ws-fanout"
CONSUMER_GROUP_ORDER_SYNC = "cg:order-sync"
CONSUMER_GROUP_WS_BOARD_FANOUT = "cg:ws-board-fanout"

# Kitchen's event types map onto the FSM event name (for the timeline) and
# the resulting status. This sets `status` directly rather than routing
# through `fsm.apply_transition` — kitchen already validated the transition
# before firing the event, and its own `queued -> prepping` step
# (`start_prep`) has no catalogue event (SPEC.md §4), so front-of-house's mirror of
# `status` intentionally coarsens `prepping` into `queued` until the next
# event it actually hears about arrives. `apply_transition`'s strict
# single-hop table is for transitions front-of-house itself still drives (place,
# accept, reject) — this handler trusts kitchen's, not re-derives them.
_EVENT_TYPE_TO_TRANSITION = {
    "order.queued": ("enqueue", "queued"),
    "order.baking": ("start_bake", "baking"),
    "order.baked": ("finish_bake", "boxed"),
    "order.ready": ("mark_ready", "ready"),
    "courier.assigned": ("assign", "assigned"),
    "order.picked_up": ("pick_up", "picked_up"),
    "order.delivering": ("depart", "delivering"),
    "order.delivered": ("deliver", "delivered"),
    "order.failed": ("fail", "failed"),
    "order.unassigned": ("unassign", "ready"),
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


def handle_board_fanout(message: StreamMessage) -> None:
    """Same `stream_id`-vs-`event_id` reasoning as `handle_ws_fanout`, but
    `group_send`s to the single fixed `"board"` group instead of a
    per-order one — there's one board, not one per aggregate. `stream` is
    derived from the catalogue rather than passed in, so it's correct
    regardless of which of the three `stream_consumer` processes (one per
    stream, same group name) happened to receive this message."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        "board",
        {
            "type": "board.event",
            "envelope": message.envelope.model_dump(mode="json"),
            "stream_id": message.message_id,
            "stream": stream_for(message.envelope.event_type),
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
        if to_status == "delivered":
            order.delivered_at = timezone.now()
        order.save()
        OrderStatusEvent.objects.create(
            order=order, from_status=from_status, to_status=to_status, event=fsm_event
        )


HANDLERS: dict[str, Callable[[StreamMessage], None]] = {
    CONSUMER_GROUP_ANALYTICS: lambda message: handle_analytics(message.envelope),
    CONSUMER_GROUP_WS_FANOUT: handle_ws_fanout,
    CONSUMER_GROUP_ORDER_SYNC: lambda message: handle_order_sync(message.envelope),
    CONSUMER_GROUP_WS_BOARD_FANOUT: handle_board_fanout,
}
