"""Write an outbox row inside the caller's own transaction (DECISIONS.md §0004).

`NOTIFY` is issued in the same transaction as the insert — Postgres only
delivers a notification once the issuing transaction commits, so this is
safe to call unconditionally rather than deferring it to an `on_commit`
hook. It's the "instant path"; the relay's poll loop is the fallback that
makes Redis loss (or a missed notification) self-healing.
"""

from uuid import UUID, uuid4

from django.db import connection
from django.utils import timezone

from dinner_rush_core.events.catalogue import stream_for
from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.observability import current_trace_context

OUTBOX_NOTIFY_CHANNEL = "outbox_channel"
PRODUCER = "front_of_house@0.1.0"


def build_envelope(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: UUID,
    sequence: int,
    correlation_id: UUID,
    payload: dict[str, object],
    causation_id: UUID | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        event_type=event_type,
        event_version=1,
        occurred_at=timezone.now(),
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        sequence=sequence,
        correlation_id=correlation_id,
        causation_id=causation_id,
        producer=PRODUCER,
        payload=payload,
        trace_context=current_trace_context(),
    )


def write_outbox_event(envelope: EventEnvelope) -> None:
    """Call inside the transaction that commits the state change this event
    announces. There must be no committed state change without its event."""
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO outbox (event_id, stream, envelope, created_at) "
        "VALUES (%s, %s, %s::jsonb, now())",
        [str(envelope.event_id), stream_for(envelope.event_type), envelope.model_dump_json()],
    )
    cursor.execute(f"NOTIFY {OUTBOX_NOTIFY_CHANNEL}")
