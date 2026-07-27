"""Consumer-side idempotency (DECISIONS.md §0004).

`mark_processed_or_skip` must run in the same transaction as the consumer's
side effect: zero rows inserted means another delivery of this event already
did the work, so the caller acks and moves on without repeating it. That
same-transaction pairing is what makes the guarantee "effectively-once for
database side effects" rather than merely "we tried to dedupe."
"""

from uuid import UUID

from dinner_rush_core.outbox.relay import Cursor


def mark_processed_or_skip(
    cursor: Cursor, consumer_group: str, event_id: UUID, *, table: str = "processed_event"
) -> bool:
    """Returns True if this delivery should proceed (first time seen)."""
    cursor.execute(
        f"INSERT INTO {table} (consumer_group, event_id, processed_at) "
        "VALUES (%s, %s, now()) ON CONFLICT DO NOTHING",
        [consumer_group, str(event_id)],
    )
    return cursor.rowcount == 1
