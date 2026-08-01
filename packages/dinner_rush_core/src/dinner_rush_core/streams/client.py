"""Redis Streams publish/consume and XAUTOCLAIM recovery (DECISIONS.md §0003).

Plain `redis-py` over the stream primitives — no framework dependency, so
this is reused unmodified by front-of-house, kitchen and dispatch alike. One
stream per aggregate type; consumer groups per subscriber (`cg:analytics`,
`cg:ws-fanout`, ...). `XAUTOCLAIM` on a timer is the entire mechanism behind
the `docker compose stop dispatch` recovery demo — a crashed consumer's
unacked messages become claimable by a live one once they've been idle past
`min_idle_ms`.

`publish` and `span_from_envelope` (Phase 9) are the one shared choke point
for OTel trace propagation across the publish/consume boundary — see their
docstrings.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from opentelemetry import context as otel_context
from opentelemetry import propagate, trace

from dinner_rush_core.events.envelope import EventEnvelope

if TYPE_CHECKING:
    from opentelemetry.trace import Span
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


def backlog(client: "Redis", stream: str, group: str) -> int:
    """`pending + lag` for one consumer group on one stream — the number the
    Phase 10 `docker compose stop dispatch` demo needs on a graph.

    `XPENDING`'s count alone is *not* this: it only counts entries a
    consumer has read via `XREADGROUP` but not yet acked — a stuck or
    crashed-mid-processing consumer, the case `XAUTOCLAIM` recovers from.
    A fully stopped consumer never issues `XREADGROUP` at all, so nothing
    ever becomes "pending" no matter how far behind the stream it falls;
    that growing gap is `XINFO GROUPS`' `lag` field instead. The backlog a
    chaos demo shows draining is both cases at once, so this sums them.
    """
    for info in client.xinfo_groups(stream):
        name = info["name"]
        if isinstance(name, bytes):
            name = name.decode()
        if name == group:
            return int(info["pending"]) + int(info.get("lag") or 0)
    return 0


def publish(client: "Redis", stream: str, envelope: EventEnvelope, *, maxlen: int = 100_000) -> str:
    """Pure transport — publishes whatever `envelope.trace_context` already
    holds, set once at `build_envelope` time in each service's own writer
    module (`dinner_rush_core.observability.current_trace_context`), never
    stamped here. The outbox relay that calls this runs in its own process
    on its own polling loop, decoupled from whatever request or task caused
    the event; there is nothing meaningful active in *this* process's OTel
    context to inject by the time a row reaches the relay.
    """
    message_id = client.xadd(
        stream,
        {_FIELD: envelope.model_dump_json()},
        maxlen=maxlen,
        approximate=True,
    )
    return message_id.decode() if isinstance(message_id, bytes) else str(message_id)


@contextmanager
def span_from_envelope(envelope: EventEnvelope, span_name: str) -> Iterator["Span"]:
    """Extracts `envelope.trace_context` and starts a child span under it.

    Every consumer loop wraps its handler dispatch in this. If the envelope
    carries no trace context (published before this field existed, or
    publisher wasn't sampled), this degrades to an ordinary new trace rather
    than raising — tracing is diagnostic, never a reason to drop a message.
    """
    parent_context = (
        propagate.extract(envelope.trace_context) if envelope.trace_context else None
    )
    tracer = trace.get_tracer("dinner_rush_core.streams")
    token = otel_context.attach(parent_context) if parent_context is not None else None
    try:
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("correlation_id", str(envelope.correlation_id))
            span.set_attribute("event_type", envelope.event_type)
            span.set_attribute("aggregate_id", str(envelope.aggregate_id))
            yield span
    finally:
        if token is not None:
            otel_context.detach(token)


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
