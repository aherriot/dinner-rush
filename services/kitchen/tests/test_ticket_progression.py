import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from dinner_rush_core.events.envelope import EventEnvelope
from kitchen.consumers import handle_order_accepted
from kitchen.models import Outbox, Oven, OvenSlot, Ticket
from kitchen.slots import count_occupied_slots
from kitchen.tasks import CLAIM_RETRY_COUNTDOWN_SECONDS, STEPS, advance_ticket


def _order_accepted_envelope(order_id: uuid.UUID) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid.uuid4(),
        event_type="order.accepted",
        event_version=1,
        occurred_at=datetime.now(UTC),
        aggregate_type="order",
        aggregate_id=order_id,
        sequence=2,
        correlation_id=order_id,
        producer="front_of_house@0.1.0",
        payload={
            "code": "4400",
            "promised_at": datetime.now(UTC).isoformat(),
            "items": [{"sku": "MARG", "qty": 1}],
        },
    )


@pytest.fixture(autouse=True)
def _menu(monkeypatch: pytest.MonkeyPatch) -> None:
    import kitchen.consumers as consumers_module
    import kitchen.tasks as tasks_module
    from dinner_rush_core.config import MenuItemConfig

    menu_items = [
        MenuItemConfig(
            sku="MARG",
            name="Margherita",
            price_cents=1200,
            prep_seconds=9,
            bake_seconds=42,
            oven_slots=1,
        )
    ]

    class _FakeConfig:
        menu = menu_items
        speed = 60

    monkeypatch.setattr(consumers_module, "load_config", lambda: _FakeConfig())
    monkeypatch.setattr(tasks_module, "load_config", lambda: _FakeConfig())
    monkeypatch.setattr(tasks_module, "_speed", lambda: 60)
    # No test here has a live Celery broker; every test drives the chain by
    # calling `advance_ticket` directly rather than through a worker, so
    # scheduling the *next* step is a no-op by default. Tests asserting on
    # scheduling override this explicitly.
    monkeypatch.setattr(advance_ticket, "apply_async", lambda *a, **kw: None)


def test_order_accepted_creates_a_queued_ticket_and_publishes_order_queued(
    session: Session,
) -> None:
    order_id = uuid.uuid4()
    handle_order_accepted(session, _order_accepted_envelope(order_id))

    ticket = session.query(Ticket).filter_by(order_id=order_id).one()
    assert ticket.status == "queued"
    assert ticket.code == "4400"
    assert ticket.total_bake_seconds == 42

    published_types = [row.envelope["event_type"] for row in session.query(Outbox).all()]
    assert "order.queued" in published_types


def test_ignores_other_event_types_sharing_the_order_stream(session: Session) -> None:
    """`events:order` carries every order event, not just `order.accepted`
    (one stream per aggregate — DECISIONS.md §0003). `order.placed`'s
    payload happens to carry the same `code`/`items` shape `order.accepted`
    does, so without an explicit type check this handler would build a
    ticket from it too — and then choke on the real `order.accepted` with a
    `UniqueViolation` on `ticket.order_id`, exactly the incident this guards
    against."""
    order_id = uuid.uuid4()
    placed = _order_accepted_envelope(order_id)
    placed = placed.model_copy(update={"event_type": "order.placed", "event_id": uuid.uuid4()})

    handle_order_accepted(session, placed)

    assert session.query(Ticket).filter_by(order_id=order_id).count() == 0

    handle_order_accepted(session, _order_accepted_envelope(order_id))
    assert session.query(Ticket).filter_by(order_id=order_id).count() == 1


def test_redelivering_order_accepted_does_not_create_a_second_ticket(session: Session) -> None:
    order_id = uuid.uuid4()
    envelope = _order_accepted_envelope(order_id)

    handle_order_accepted(session, envelope)
    handle_order_accepted(session, envelope)

    assert session.query(Ticket).filter_by(order_id=order_id).count() == 1


def test_ticket_walks_all_the_way_to_ready_and_frees_its_oven_slot(session: Session) -> None:
    oven = Oven(name="Test Oven", slot_count=1, status="available")
    session.add(oven)
    session.flush()
    session.add(OvenSlot(oven_id=oven.id, slot_index=0))
    session.commit()

    order_id = uuid.uuid4()
    handle_order_accepted(session, _order_accepted_envelope(order_id))
    ticket = session.query(Ticket).filter_by(order_id=order_id).one()

    causation_id = None
    for step_index in range(len(STEPS)):
        advance_ticket(
            str(ticket.id), step_index, sequence=10 + step_index, causation_id=causation_id
        )
        rows = session.query(Outbox).order_by(Outbox.id).all()
        if rows:
            causation_id = str(rows[-1].event_id)

    session.refresh(ticket)
    assert ticket.status == "ready"
    assert ticket.oven_slot_id is not None
    assert count_occupied_slots(session) == 0  # released on finish_bake

    published_types = [row.envelope["event_type"] for row in session.query(Outbox).all()]
    assert published_types == [
        "order.queued",
        "order.baking",
        "order.baked",
        "oven.slot_freed",
        "order.ready",
    ]


def test_start_bake_retries_with_backoff_when_the_oven_is_full(
    monkeypatch: pytest.MonkeyPatch, session: Session
) -> None:
    # No oven at all — every claim attempt fails.
    order_id = uuid.uuid4()
    handle_order_accepted(session, _order_accepted_envelope(order_id))
    ticket = session.query(Ticket).filter_by(order_id=order_id).one()
    ticket.status = "prepping"
    session.commit()

    retried_args = []
    monkeypatch.setattr(
        advance_ticket,
        "apply_async",
        lambda args, countdown: retried_args.append((args, countdown)),
    )
    advance_ticket(str(ticket.id), 1, sequence=11, causation_id=None)  # start_bake: no oven

    session.refresh(ticket)
    assert ticket.status == "prepping"  # never advanced to baking
    assert len(retried_args) == 1
    assert retried_args[0][0] == (str(ticket.id), 1, 11, None)
    # Retry countdown is domain-seconds, scaled by SPEED at the point of use
    # like every other delay in this module (SPEC.md §5) — at speed=60 a
    # fixed 5s wall-clock retry would make contention recovery ~60x slower
    # than every other step in the pipeline.
    assert retried_args[0][1] == pytest.approx(CLAIM_RETRY_COUNTDOWN_SECONDS / 60)
