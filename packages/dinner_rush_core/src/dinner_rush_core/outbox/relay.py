"""The transactional outbox relay (DECISIONS.md §0004).

Framework-agnostic on purpose: it takes a plain DB-API cursor (psycopg via
Django today; a raw SQLAlchemy connection's cursor once kitchen and dispatch
exist in Phase 4/7) rather than an ORM model, so the same relay loop is
reused unmodified by every service instead of being rewritten per framework.

Each service owns its own `outbox` table (same shape, separate database —
CLAUDE.md §3, "each service owns its own Postgres database"), created by
that service's own migrations. This module only knows the shape of the row.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from dinner_rush_core.events.envelope import EventEnvelope


class Cursor(Protocol):
    def execute(self, sql: str, params: Sequence[Any]) -> None: ...
    def fetchall(self) -> Sequence[Sequence[Any]]: ...
    @property
    def rowcount(self) -> int: ...


@dataclass(frozen=True)
class OutboxRow:
    id: int
    event_id: UUID
    stream: str
    envelope: EventEnvelope


def fetch_unpublished(
    cursor: Cursor, *, table: str = "outbox", limit: int = 100
) -> list[OutboxRow]:
    """`SKIP LOCKED` so multiple relay workers parallelise safely."""
    cursor.execute(
        f"SELECT id, event_id, stream, envelope FROM {table} "
        "WHERE published_at IS NULL ORDER BY id FOR UPDATE SKIP LOCKED LIMIT %s",
        [limit],
    )
    rows = cursor.fetchall()
    return [
        OutboxRow(
            id=row[0],
            event_id=row[1],
            stream=row[2],
            envelope=EventEnvelope.model_validate(
                row[3] if isinstance(row[3], dict) else json.loads(row[3])
            ),
        )
        for row in rows
    ]


def mark_published(cursor: Cursor, ids: Sequence[int], *, table: str = "outbox") -> None:
    if not ids:
        return
    cursor.execute(
        f"UPDATE {table} SET published_at = now() WHERE id = ANY(%s)",
        [list(ids)],
    )


def relay_batch(
    cursor: Cursor,
    publish: Callable[[OutboxRow], None],
    *,
    table: str = "outbox",
    limit: int = 100,
) -> int:
    """One relay pass. Call inside the transaction that owns `cursor`.

    At-least-once, deliberately: if the process dies after `publish` but
    before the caller commits `mark_published`, the same rows relay again on
    the next pass. Consumers dedupe by `event_id` (see
    `dinner_rush_core.outbox.idempotency`), so a duplicate publish is
    harmless rather than a bug — precisely the guarantee DECISIONS.md §0004
    states rather than hides.
    """
    rows = fetch_unpublished(cursor, table=table, limit=limit)
    for row in rows:
        publish(row)
    mark_published(cursor, [row.id for row in rows], table=table)
    return len(rows)
