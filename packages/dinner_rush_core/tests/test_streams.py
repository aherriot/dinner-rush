import datetime
import os
import uuid
from collections.abc import Iterator

import pytest
import redis

from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.streams import ack, autoclaim, ensure_group, publish, read_batch, read_range


def _envelope(sequence: int = 1) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid.uuid4(),
        event_type="order.placed",
        event_version=1,
        occurred_at=datetime.datetime.now(datetime.UTC),
        aggregate_type="order",
        aggregate_id=uuid.uuid4(),
        sequence=sequence,
        correlation_id=uuid.uuid4(),
        producer="gateway@0.1.0",
        payload={"code": "4400"},
    )


@pytest.fixture
def client() -> Iterator[redis.Redis]:
    conn = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    yield conn
    conn.close()


@pytest.fixture
def stream(client: redis.Redis) -> Iterator[str]:
    name = f"test:events:{uuid.uuid4()}"
    yield name
    client.delete(name)


def test_publish_then_read_batch_delivers_the_envelope(client: redis.Redis, stream: str) -> None:
    group = "cg:test-consumer"
    ensure_group(client, stream, group)
    envelope = _envelope()
    publish(client, stream, envelope)

    messages = read_batch(client, stream, group, "worker-1", block_ms=100)

    assert len(messages) == 1
    assert messages[0].envelope.event_id == envelope.event_id


def test_acked_message_is_not_redelivered(client: redis.Redis, stream: str) -> None:
    group = "cg:test-consumer"
    ensure_group(client, stream, group)
    publish(client, stream, _envelope())
    messages = read_batch(client, stream, group, "worker-1", block_ms=100)
    ack(client, stream, group, [m.message_id for m in messages])

    pending = client.xpending(stream, group)
    assert pending["pending"] == 0


def test_unacked_message_is_reclaimed_by_autoclaim_after_it_goes_idle(
    client: redis.Redis, stream: str
) -> None:
    """Simulates 'kill a consumer mid-stream': worker-1 reads but crashes
    before acking. After it's been idle past the threshold, worker-2 claims
    it via XAUTOCLAIM and finishes the job — the mechanism behind the
    `docker compose stop dispatch` recovery demo (DECISIONS.md §0003)."""
    group = "cg:test-consumer"
    ensure_group(client, stream, group)
    envelope = _envelope()
    publish(client, stream, envelope)

    crashed_worker_messages = read_batch(client, stream, group, "worker-1", block_ms=100)
    assert len(crashed_worker_messages) == 1  # read, never acked — the "crash"

    reclaimed = autoclaim(client, stream, group, "worker-2", min_idle_ms=0)

    assert len(reclaimed) == 1
    assert reclaimed[0].envelope.event_id == envelope.event_id
    ack(client, stream, group, [m.message_id for m in reclaimed])
    assert client.xpending(stream, group)["pending"] == 0


def test_read_range_replays_strictly_after_last_seen_id(client: redis.Redis, stream: str) -> None:
    first_id = publish(client, stream, _envelope(sequence=1))
    second = _envelope(sequence=2)
    publish(client, stream, second)

    replayed = read_range(client, stream, first_id)

    assert [m.envelope.event_id for m in replayed] == [second.event_id]


def test_read_range_from_the_beginning_replays_everything(client: redis.Redis, stream: str) -> None:
    envelopes = [_envelope(sequence=i) for i in range(3)]
    for envelope in envelopes:
        publish(client, stream, envelope)

    replayed = read_range(client, stream, "-")

    assert [m.envelope.event_id for m in replayed] == [e.event_id for e in envelopes]
