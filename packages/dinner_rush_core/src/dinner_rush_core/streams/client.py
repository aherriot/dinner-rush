"""Redis Streams publish/consume and XAUTOCLAIM recovery (DECISIONS.md §0003).

Plain `redis-py` over the stream primitives — no framework dependency, so
this is reused unmodified by front-of-house today and by kitchen/dispatch once they
exist. One stream per aggregate type; consumer groups per subscriber
(`cg:analytics`, `cg:ws-fanout`, ...). `XAUTOCLAIM` on a timer is the entire
mechanism behind the `docker compose stop dispatch` recovery demo — a
crashed consumer's unacked messages become claimable by a live one once
they've been idle past `min_idle_ms`.
"""

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from dinner_rush_core.events.envelope import EventEnvelope

if TYPE_CHECKING:
    from redis import Redis

_FIELD = "envelope"
# redis-py's own type stubs describe these return shapes as broad unions
# covering every call variant (return_json, etc.); the casts below pin them
# to the one shape these calls actually produce at runtime.
_Entries = list[tuple[Any, dict[Any, Any]]]


@dataclass(frozen=True)
class StreamMessage:
    message_id: str
    envelope: EventEnvelope


def _decode(raw_fields: dict[Any, Any]) -> EventEnvelope:
    raw = raw_fields[_FIELD] if _FIELD in raw_fields else raw_fields[_FIELD.encode()]
    if isinstance(raw, bytes):
        raw = raw.decode()
    return EventEnvelope.model_validate(json.loads(raw))


def ensure_group(client: "Redis", stream: str, group: str) -> None:
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
    except Exception as exc:  # redis.ResponseError: BUSYGROUP
        if "BUSYGROUP" not in str(exc):
            raise


def publish(client: "Redis", stream: str, envelope: EventEnvelope, *, maxlen: int = 100_000) -> str:
    message_id = client.xadd(
        stream,
        {_FIELD: envelope.model_dump_json()},
        maxlen=maxlen,
        approximate=True,
    )
    return message_id.decode() if isinstance(message_id, bytes) else str(message_id)


def read_batch(
    client: "Redis",
    stream: str,
    group: str,
    consumer: str,
    *,
    count: int = 64,
    block_ms: int = 2000,
) -> list[StreamMessage]:
    response = client.xreadgroup(group, consumer, {stream: ">"}, count=count, block=block_ms)
    if not response:
        return []
    per_stream = cast(list[tuple[Any, _Entries]], response)
    _, entries = per_stream[0]
    return _to_messages(entries)


def ack(client: "Redis", stream: str, group: str, message_ids: list[str]) -> None:
    if message_ids:
        client.xack(stream, group, *message_ids)


def autoclaim(
    client: "Redis",
    stream: str,
    group: str,
    consumer: str,
    *,
    min_idle_ms: int,
    count: int = 64,
) -> list[StreamMessage]:
    """Reclaim messages pending longer than `min_idle_ms` from dead consumers."""
    _next_cursor, claimed, _deleted = client.xautoclaim(
        stream, group, consumer, min_idle_ms, start_id="0-0", count=count
    )
    return _to_messages(cast(_Entries, claimed))


def read_range(
    client: "Redis", stream: str, start_id: str, end_id: str = "+"
) -> list[StreamMessage]:
    """`XRANGE`, exclusive of `start_id` — the websocket replay primitive.

    Redis's own `(id` exclusive-range syntax does the "strictly after"
    filtering; callers pass the client's last-seen id verbatim.
    """
    entries = client.xrange(stream, min=f"({start_id}" if start_id != "-" else "-", max=end_id)
    return _to_messages(cast(_Entries, entries))


def _to_messages(entries: _Entries) -> list[StreamMessage]:
    return [
        StreamMessage(message_id=_mid(mid), envelope=_decode(fields)) for mid, fields in entries
    ]


def _mid(message_id: bytes | str) -> str:
    return message_id.decode() if isinstance(message_id, bytes) else message_id
