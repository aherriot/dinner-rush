"""Consumer group handlers, keyed by group name (SPEC.md §4 classification).

Two groups, two different guarantees, deliberately:

- `cg:analytics` writes to Postgres and must be effectively-once, so it
  dedupes via `processed_event` in the same transaction as its side effect
  (an `EventTypeCounter` increment — small enough to write a clean
  redelivery-is-a-no-op test against).
- `cg:ws-fanout` pushes to an in-memory Channels group and is at-least-once
  by design; the browser dedupes by `event_id` client-side, so there is
  nothing to make idempotent server-side.
"""

from collections.abc import Callable

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection, transaction

from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.outbox import mark_processed_or_skip
from gateway.eventing.models import EventTypeCounter

CONSUMER_GROUP_ANALYTICS = "cg:analytics"
CONSUMER_GROUP_WS_FANOUT = "cg:ws-fanout"


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


def handle_ws_fanout(envelope: EventEnvelope) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"order.{envelope.aggregate_id}",
        {"type": "order.event", "envelope": envelope.model_dump(mode="json")},
    )


HANDLERS: dict[str, Callable[[EventEnvelope], None]] = {
    CONSUMER_GROUP_ANALYTICS: handle_analytics,
    CONSUMER_GROUP_WS_FANOUT: handle_ws_fanout,
}
