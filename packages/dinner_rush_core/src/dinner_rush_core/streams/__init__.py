"""Redis Streams publish/consume and XAUTOCLAIM recovery (DECISIONS.md §0003)."""

from dinner_rush_core.streams.client import (
    StreamMessage,
    ack,
    autoclaim,
    backlog,
    ensure_group,
    publish,
    read_batch,
    read_range,
    span_from_envelope,
)

__all__ = [
    "StreamMessage",
    "ack",
    "autoclaim",
    "backlog",
    "ensure_group",
    "publish",
    "read_batch",
    "read_range",
    "span_from_envelope",
]
