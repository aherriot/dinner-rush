"""Write an outbox row inside the caller's own transaction (DECISIONS.md §0004).

Same pattern as `gateway.eventing.writer` and `kitchen.writer` — same table
shape, different database — dispatch's own `outbox` table, never gateway's
or kitchen's.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from dinner_rush_core.events.catalogue import stream_for
from dinner_rush_core.events.envelope import EventEnvelope
from dispatch.dbapi import raw_cursor

OUTBOX_NOTIFY_CHANNEL = "outbox_channel"
PRODUCER = "dispatch@0.1.0"


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
        occurred_at=datetime.now(UTC),
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        sequence=sequence,
        correlation_id=correlation_id,
        causation_id=causation_id,
        producer=PRODUCER,
        payload=payload,
    )


def write_outbox_event(session: Session, envelope: EventEnvelope) -> None:
    cursor = raw_cursor(session)
    cursor.execute(
        "INSERT INTO outbox (event_id, stream, envelope, created_at) "
        "VALUES (%s, %s, %s::jsonb, now())",
        [str(envelope.event_id), stream_for(envelope.event_type), envelope.model_dump_json()],
    )
    cursor.execute(f"NOTIFY {OUTBOX_NOTIFY_CHANNEL}")
