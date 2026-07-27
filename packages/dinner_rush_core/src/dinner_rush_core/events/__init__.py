"""Event envelope and schema catalogue (SPEC.md §4, DECISIONS.md §0004)."""

from dinner_rush_core.events.catalogue import (
    EVENT_CATALOGUE,
    UnknownEventTypeError,
    stream_for,
    validate_payload,
)
from dinner_rush_core.events.envelope import EventEnvelope

__all__ = [
    "EVENT_CATALOGUE",
    "EventEnvelope",
    "UnknownEventTypeError",
    "stream_for",
    "validate_payload",
]
