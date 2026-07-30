import datetime
import uuid
from typing import Any

from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.outbox import fetch_unpublished, mark_processed_or_skip, relay_batch


def _envelope() -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid.uuid4(),
        event_type="order.placed",
        event_version=1,
        occurred_at=datetime.datetime.now(datetime.UTC),
        aggregate_type="order",
        aggregate_id=uuid.uuid4(),
        sequence=1,
        correlation_id=uuid.uuid4(),
        producer="front_of_house@0.1.0",
        payload={"code": "4400"},
    )


class FakeOutboxCursor:
    """Stands in for a psycopg/SQLAlchemy cursor against an `outbox` table.

    Good enough for exercising the relay's *logic* (which rows it selects,
    what it marks published) without a live Postgres — the SKIP LOCKED
    concurrency behaviour itself is a database property, proven against the
    real thing in the front-of-house-level tests.
    """

    def __init__(self, rows: list[tuple[int, uuid.UUID, str, dict[str, Any], bool]]) -> None:
        self._rows = rows  # (id, event_id, stream, envelope_dict, published)
        self.rowcount = 0
        self._last_select: list[tuple[int, uuid.UUID, str, dict[str, Any]]] = []

    def execute(self, sql: str, params: list[Any]) -> None:
        if sql.startswith("SELECT"):
            limit = params[0]
            unpublished = [row for row in self._rows if not row[4]]
            self._last_select = [(r[0], r[1], r[2], r[3]) for r in unpublished[:limit]]
        elif sql.startswith("UPDATE"):
            ids = set(params[0])
            for i, row in enumerate(self._rows):
                if row[0] in ids:
                    self._rows[i] = (*row[:4], True)
            self.rowcount = len(ids)

    def fetchall(self) -> list[tuple[int, uuid.UUID, str, dict[str, Any]]]:
        return self._last_select


def test_fetch_unpublished_skips_rows_already_marked_published() -> None:
    published_envelope = _envelope()
    unpublished_envelope = _envelope()
    cursor = FakeOutboxCursor(
        [
            (
                1,
                published_envelope.event_id,
                "events:order",
                published_envelope.model_dump(mode="json"),
                True,
            ),
            (
                2,
                unpublished_envelope.event_id,
                "events:order",
                unpublished_envelope.model_dump(mode="json"),
                False,
            ),
        ]
    )

    rows = fetch_unpublished(cursor, limit=100)  # type: ignore[arg-type]

    assert [row.id for row in rows] == [2]
    assert rows[0].envelope.event_id == unpublished_envelope.event_id


def test_relay_batch_publishes_each_unpublished_row_once_and_marks_it() -> None:
    envelopes = [_envelope(), _envelope()]
    cursor = FakeOutboxCursor(
        [
            (i + 1, e.event_id, "events:order", e.model_dump(mode="json"), False)
            for i, e in enumerate(envelopes)
        ]
    )
    published_event_ids = []

    count = relay_batch(cursor, lambda row: published_event_ids.append(row.event_id))  # type: ignore[arg-type]

    assert count == 2
    assert set(published_event_ids) == {e.event_id for e in envelopes}
    assert all(row[4] for row in cursor._rows)  # every row now marked published


def test_relay_batch_is_a_no_op_when_nothing_is_unpublished() -> None:
    cursor = FakeOutboxCursor([])
    calls = []

    count = relay_batch(cursor, lambda row: calls.append(row))  # type: ignore[arg-type]

    assert count == 0
    assert calls == []


class FakeProcessedEventCursor:
    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()
        self.rowcount = 0

    def execute(self, sql: str, params: list[Any]) -> None:
        key = (params[0], params[1])
        if key in self._seen:
            self.rowcount = 0
        else:
            self._seen.add(key)
            self.rowcount = 1

    def fetchall(self) -> list[Any]:
        return []


def test_mark_processed_or_skip_returns_true_only_on_first_delivery() -> None:
    cursor = FakeProcessedEventCursor()
    event_id = uuid.uuid4()

    first = mark_processed_or_skip(cursor, "cg:analytics", event_id)  # type: ignore[arg-type]
    redelivered = mark_processed_or_skip(cursor, "cg:analytics", event_id)  # type: ignore[arg-type]

    assert first is True
    assert redelivered is False


def test_mark_processed_or_skip_is_scoped_per_consumer_group() -> None:
    cursor = FakeProcessedEventCursor()
    event_id = uuid.uuid4()

    seen_by_analytics = mark_processed_or_skip(cursor, "cg:analytics", event_id)  # type: ignore[arg-type]
    seen_by_ws_fanout = mark_processed_or_skip(cursor, "cg:ws-fanout", event_id)  # type: ignore[arg-type]

    assert seen_by_analytics is True
    assert seen_by_ws_fanout is True
