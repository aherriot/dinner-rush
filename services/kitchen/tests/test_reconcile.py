import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from kitchen.models import Ticket
from kitchen.reconcile import reconcile_stuck_tickets
from kitchen.tasks import advance_ticket


@pytest.fixture(autouse=True)
def _menu(monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr(tasks_module, "load_config", lambda: _FakeConfig())


def _make_ticket(session: Session, *, status: str, queued_at: datetime) -> Ticket:
    ticket = Ticket(
        order_id=uuid.uuid4(),
        code="4400",
        status=status,
        items=[{"sku": "MARG", "qty": 1}],
        total_bake_seconds=42,
        queued_at=queued_at,
    )
    session.add(ticket)
    session.commit()
    return ticket


def _write_outbox_event(session: Session, *, order_id: uuid.UUID, sequence: int) -> uuid.UUID:
    from kitchen.writer import build_envelope, write_outbox_event

    envelope = build_envelope(
        event_type="order.queued",
        aggregate_type="order",
        aggregate_id=order_id,
        sequence=sequence,
        correlation_id=order_id,
        payload={"code": "4400"},
    )
    write_outbox_event(session, envelope)
    session.commit()
    return envelope.event_id


def test_resumes_a_ticket_that_overran_its_expected_step_duration(
    monkeypatch: pytest.MonkeyPatch, session: Session
) -> None:
    # start_bake's expected delay is start_prep's fixed 3s + 9s prep = 12s;
    # queued long enough ago that even generous grace is exceeded.
    ticket = _make_ticket(
        session, status="prepping", queued_at=datetime.now(UTC) - timedelta(seconds=120)
    )
    last_event_id = _write_outbox_event(session, order_id=ticket.order_id, sequence=5)

    scheduled = []
    monkeypatch.setattr(
        advance_ticket, "apply_async", lambda args, countdown: scheduled.append((args, countdown))
    )

    result = reconcile_stuck_tickets(session, grace_seconds=30, speed=1)

    assert [r.code for r in result] == ["4400"]
    assert len(scheduled) == 1
    args, countdown = scheduled[0]
    assert args == (str(ticket.id), 1, 6, str(last_event_id))
    assert countdown == 0


def test_leaves_a_ticket_alone_while_still_within_its_expected_window(
    monkeypatch: pytest.MonkeyPatch, session: Session
) -> None:
    ticket = _make_ticket(session, status="prepping", queued_at=datetime.now(UTC))
    _write_outbox_event(session, order_id=ticket.order_id, sequence=5)

    scheduled = []
    monkeypatch.setattr(
        advance_ticket, "apply_async", lambda args, countdown: scheduled.append((args, countdown))
    )

    result = reconcile_stuck_tickets(session, grace_seconds=30, speed=1)

    assert result == []
    assert scheduled == []


def test_skips_a_stuck_ticket_with_no_outbox_history_rather_than_guess(
    monkeypatch: pytest.MonkeyPatch, session: Session
) -> None:
    _make_ticket(session, status="prepping", queued_at=datetime.now(UTC) - timedelta(seconds=120))

    scheduled = []
    monkeypatch.setattr(
        advance_ticket, "apply_async", lambda args, countdown: scheduled.append((args, countdown))
    )

    result = reconcile_stuck_tickets(session, grace_seconds=30, speed=1)

    assert result == []
    assert scheduled == []


def test_leaves_a_ready_ticket_alone(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    _make_ticket(session, status="ready", queued_at=datetime.now(UTC) - timedelta(hours=1))

    scheduled = []
    monkeypatch.setattr(
        advance_ticket, "apply_async", lambda args, countdown: scheduled.append((args, countdown))
    )

    result = reconcile_stuck_tickets(session, grace_seconds=30, speed=1)

    assert result == []
    assert scheduled == []
