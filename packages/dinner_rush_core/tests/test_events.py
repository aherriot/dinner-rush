import datetime
import uuid

import pytest
from pydantic import ValidationError

from dinner_rush_core.events import (
    EVENT_CATALOGUE,
    EventEnvelope,
    UnknownEventTypeError,
    stream_for,
    validate_payload,
)


def _envelope(event_type: str, payload: dict[str, object]) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid.uuid4(),
        event_type=event_type,
        event_version=EVENT_CATALOGUE[event_type].version,
        occurred_at=datetime.datetime.now(datetime.UTC),
        aggregate_type="order",
        aggregate_id=uuid.uuid4(),
        sequence=1,
        correlation_id=uuid.uuid4(),
        producer="front_of_house@0.1.0",
        payload=payload,
    )


def test_order_placed_round_trips_through_json() -> None:
    envelope = _envelope(
        "order.placed",
        {
            "code": "4400",
            "customer_id": str(uuid.uuid4()),
            "items": [{"sku": "MARG", "qty": 2}],
            "total_cents": 2400,
            "grid_x": 10,
            "grid_y": 20,
        },
    )

    restored = EventEnvelope.model_validate_json(envelope.model_dump_json())

    assert restored == envelope
    assert stream_for(envelope.event_type) == "events:order"


def test_validate_payload_ignores_unknown_fields_additive_only() -> None:
    payload = validate_payload(
        "order.rejected", {"code": "4400", "reason": "at_capacity", "queue_depth": 12, "extra": "x"}
    )
    assert payload.model_dump()["reason"] == "at_capacity"  # type: ignore[attr-defined]


def test_validate_payload_rejects_missing_fields() -> None:
    with pytest.raises(ValidationError):
        validate_payload("order.rejected", {"code": "4400"})


def test_unknown_event_type_raises() -> None:
    with pytest.raises(UnknownEventTypeError):
        stream_for("order.teleported")
    with pytest.raises(UnknownEventTypeError):
        validate_payload("order.teleported", {})


def test_every_catalogue_entry_is_reachable_by_stream_and_schema() -> None:
    for event_type, schema in EVENT_CATALOGUE.items():
        assert stream_for(event_type) == schema.stream
        assert issubclass(schema.payload_model, object)
