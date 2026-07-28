import uuid
from collections.abc import Iterator

import pytest
import redis as redis_lib
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection, transaction

from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.outbox import relay_batch
from dinner_rush_core.streams import (
    StreamMessage,
    ack,
    autoclaim,
    ensure_group,
    publish,
    read_batch,
)
from gateway.eventing.handlers import handle_analytics, handle_ws_fanout
from gateway.eventing.models import EventTypeCounter, Outbox, ProcessedEvent
from gateway.eventing.redis_client import get_redis_client
from gateway.eventing.writer import build_envelope, write_outbox_event


@pytest.fixture
def redis_client() -> Iterator[redis_lib.Redis]:
    client = get_redis_client()
    yield client


@pytest.fixture
def isolated_stream(redis_client: redis_lib.Redis) -> Iterator[str]:
    """A throwaway stream, not the real `events:order` — this test exercises
    the recovery *mechanics* against the gateway's real handler, and using a
    scratch stream keeps it from colliding with whatever a running demo
    stack has already published."""
    name = f"test:events:{uuid.uuid4()}"
    yield name
    redis_client.delete(name)


@pytest.mark.django_db(transaction=True)
def test_write_outbox_event_is_visible_to_the_relay_and_gets_marked_published() -> None:
    envelope = build_envelope(
        event_type="order.placed",
        aggregate_type="order",
        aggregate_id=uuid.uuid4(),
        sequence=1,
        correlation_id=uuid.uuid4(),
        payload={
            "code": "5000",
            "customer_id": str(uuid.uuid4()),
            "items": [],
            "total_cents": 1000,
            "grid_x": 1,
            "grid_y": 1,
        },
    )
    with transaction.atomic():
        write_outbox_event(envelope)

    published = []
    with transaction.atomic():
        count = relay_batch(connection.cursor(), lambda row: published.append(row.event_id))

    assert count == 1
    assert published == [envelope.event_id]
    assert Outbox.objects.get(event_id=envelope.event_id).published_at is not None


@pytest.mark.django_db(transaction=True)
def test_relay_does_not_republish_rows_already_marked_published() -> None:
    envelope = build_envelope(
        event_type="order.placed",
        aggregate_type="order",
        aggregate_id=uuid.uuid4(),
        sequence=1,
        correlation_id=uuid.uuid4(),
        payload={
            "code": "5001",
            "customer_id": str(uuid.uuid4()),
            "items": [],
            "total_cents": 1000,
            "grid_x": 1,
            "grid_y": 1,
        },
    )
    with transaction.atomic():
        write_outbox_event(envelope)
    with transaction.atomic():
        relay_batch(connection.cursor(), lambda row: None)

    second_pass_publishes = []
    with transaction.atomic():
        count = relay_batch(connection.cursor(), lambda row: second_pass_publishes.append(row))

    assert count == 0
    assert second_pass_publishes == []


def _envelope() -> EventEnvelope:
    return build_envelope(
        event_type="order.baked",
        aggregate_type="order",
        aggregate_id=uuid.uuid4(),
        sequence=1,
        correlation_id=uuid.uuid4(),
        payload={"code": "5002", "actual_bake_s": 42.0},
    )


@pytest.mark.django_db(transaction=True)
def test_handle_analytics_redelivery_is_a_no_op() -> None:
    """The redelivery-is-a-no-op test PHASES.md Phase 3 asks for."""
    envelope = _envelope()

    handle_analytics(envelope)
    handle_analytics(envelope)  # simulates the same message delivered twice

    counter = EventTypeCounter.objects.get(event_type="order.baked")
    assert counter.count == 1
    assert ProcessedEvent.objects.filter(consumer_group="cg:analytics").count() == 1


@pytest.mark.django_db(transaction=True)
def test_handle_analytics_is_scoped_per_event_type() -> None:
    handle_analytics(_envelope())
    handle_analytics(_envelope())

    counter = EventTypeCounter.objects.get(event_type="order.baked")
    assert counter.count == 2  # two distinct events, both counted


@pytest.mark.django_db(transaction=True)
def test_a_message_left_unacked_by_a_crashed_consumer_is_reclaimed_and_processed_once(
    redis_client: redis_lib.Redis, isolated_stream: str
) -> None:
    """The `docker compose stop <consumer>` recovery mechanism, end to end:
    a message read but never acked (the "crash") gets claimed by a second
    worker via XAUTOCLAIM and its Postgres side effect still lands exactly
    once, because the handler dedupes on `event_id` regardless of which
    worker finally processes it."""
    group = "cg:test-analytics"
    ensure_group(redis_client, isolated_stream, group)
    envelope = _envelope()
    publish(redis_client, isolated_stream, envelope)

    crashed = read_batch(redis_client, isolated_stream, group, "worker-1", block_ms=100)
    assert len(crashed) == 1  # read, never acked

    reclaimed = autoclaim(redis_client, isolated_stream, group, "worker-2", min_idle_ms=0)
    assert len(reclaimed) == 1

    handle_analytics(reclaimed[0].envelope)
    ack(redis_client, isolated_stream, group, [reclaimed[0].message_id])

    assert redis_client.xpending(isolated_stream, group)["pending"] == 0
    assert EventTypeCounter.objects.get(event_type="order.baked").count == 1


@pytest.mark.django_db(transaction=True)
def test_handle_ws_fanout_pushes_to_the_orders_channel_group() -> None:
    envelope = _envelope()
    channel_layer = get_channel_layer()
    group_name = f"order.{envelope.aggregate_id}"
    async_to_sync(channel_layer.group_add)(group_name, "test-channel")

    handle_ws_fanout(StreamMessage(message_id="1700000000000-0", envelope=envelope))

    message = async_to_sync(channel_layer.receive)("test-channel")
    assert message["type"] == "order.event"
    assert message["envelope"]["event_id"] == str(envelope.event_id)


@pytest.mark.django_db(transaction=True)
def test_handle_ws_fanout_sends_the_real_stream_id_not_the_envelopes_event_id() -> None:
    """Regression test: the browser echoes this value back as
    `?last_event_id=` on reconnect, and only a genuine Redis stream id
    (`<ms>-<seq>`) survives `XRANGE` there — the envelope's own `event_id`
    is an unrelated business UUID and crashes the websocket consumer when
    sent back (see `test_replay_...` in test_consumers.py for the other
    half of this regression)."""
    envelope = _envelope()
    channel_layer = get_channel_layer()
    group_name = f"order.{envelope.aggregate_id}"
    async_to_sync(channel_layer.group_add)(group_name, "test-channel")

    handle_ws_fanout(StreamMessage(message_id="1700000000000-0", envelope=envelope))

    message = async_to_sync(channel_layer.receive)("test-channel")
    assert message["stream_id"] == "1700000000000-0"
    assert message["stream_id"] != str(envelope.event_id)
