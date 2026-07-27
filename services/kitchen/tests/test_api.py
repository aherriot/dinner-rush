import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from kitchen.db import get_session
from kitchen.main import app
from kitchen.models import Oven, OvenSlot, Ticket


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_healthz_is_always_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_postgres_and_redis(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["postgres"] == "ok"


def test_queue_lists_tickets_by_priority_then_queued_at(
    session: Session, client: TestClient
) -> None:
    low = Ticket(
        order_id=uuid.uuid4(),
        code="1000",
        items=[],
        total_bake_seconds=60,
        queued_at=datetime.now(UTC),
        priority=0,
    )
    high = Ticket(
        order_id=uuid.uuid4(),
        code="1001",
        items=[],
        total_bake_seconds=60,
        queued_at=datetime.now(UTC),
        priority=5,
    )
    session.add_all([low, high])
    session.commit()

    response = client.get("/queue")
    assert response.status_code == 200
    codes = [ticket["code"] for ticket in response.json()]
    assert codes == ["1001", "1000"]


def test_queue_excludes_ready_tickets(session: Session, client: TestClient) -> None:
    ticket = Ticket(
        order_id=uuid.uuid4(),
        code="1002",
        status="ready",
        items=[],
        total_bake_seconds=60,
        queued_at=datetime.now(UTC),
    )
    session.add(ticket)
    session.commit()

    response = client.get("/queue")
    assert response.json() == []


def test_ovens_reports_slot_occupancy(session: Session, client: TestClient) -> None:
    oven = Oven(name="Oven 1", slot_count=2, status="available")
    session.add(oven)
    session.flush()
    session.add(OvenSlot(oven_id=oven.id, slot_index=0, order_id=uuid.uuid4()))
    session.add(OvenSlot(oven_id=oven.id, slot_index=1))
    session.commit()

    response = client.get("/ovens")
    assert response.status_code == 200
    [body] = response.json()
    assert body["name"] == "Oven 1"
    assert len(body["slots"]) == 2
    assert body["slots"][0]["order_id"] is not None
    assert body["slots"][1]["order_id"] is None


def test_capacity_quote_accepts_when_ovens_are_free(session: Session, client: TestClient) -> None:
    oven = Oven(name="Oven 1", slot_count=6, status="available")
    session.add(oven)
    session.flush()
    session.add(OvenSlot(oven_id=oven.id, slot_index=0))
    session.commit()

    response = client.post("/capacity/quote", json={"items": [{"sku": "MARG", "qty": 1}]})
    assert response.status_code == 200
    body = response.json()
    assert body["can_accept"] is True
    assert body["queue_depth"] == 0


def test_capacity_quote_rejects_unknown_sku(client: TestClient) -> None:
    response = client.post("/capacity/quote", json={"items": [{"sku": "NOPE", "qty": 1}]})
    assert response.status_code == 422


def test_capacity_quote_rejects_at_max_queue_depth(
    monkeypatch: pytest.MonkeyPatch, session: Session, client: TestClient
) -> None:
    import kitchen.routers.capacity as capacity_router
    from dinner_rush_core.config import CapacityConfig, MenuItemConfig

    menu_items = [
        MenuItemConfig(
            sku="MARG",
            name="Margherita",
            price_cents=1200,
            prep_seconds=90,
            bake_seconds=420,
            oven_slots=1,
        )
    ]
    tight_capacity = CapacityConfig(
        max_queue_depth=1,
        max_projected_wait_seconds=2700,
        promise_buffer_seconds=180,
        reject_when_all_ovens_down=True,
    )

    class _FakeKitchenConfig:
        capacity = tight_capacity

    class _FakeConfig:
        menu = menu_items
        kitchen = _FakeKitchenConfig()

    monkeypatch.setattr(capacity_router, "load_config", lambda: _FakeConfig())

    oven = Oven(name="Oven 1", slot_count=6, status="available")
    session.add(oven)
    session.flush()
    session.add(OvenSlot(oven_id=oven.id, slot_index=0))
    session.add(
        Ticket(
            order_id=uuid.uuid4(),
            code="2000",
            items=[],
            total_bake_seconds=60,
            queued_at=datetime.now(UTC),
        )
    )
    session.commit()

    response = client.post("/capacity/quote", json={"items": [{"sku": "MARG", "qty": 1}]})
    assert response.json()["can_accept"] is False


def test_tickets_advance_applies_a_legal_transition(session: Session, client: TestClient) -> None:
    ticket = Ticket(
        order_id=uuid.uuid4(),
        code="3000",
        items=[],
        total_bake_seconds=60,
        queued_at=datetime.now(UTC),
    )
    session.add(ticket)
    session.commit()

    response = client.post(f"/tickets/{ticket.id}/advance", json={"event": "start_prep"})
    assert response.status_code == 200
    assert response.json()["status"] == "prepping"


def test_tickets_advance_rejects_an_illegal_transition(
    session: Session, client: TestClient
) -> None:
    ticket = Ticket(
        order_id=uuid.uuid4(),
        code="3001",
        items=[],
        total_bake_seconds=60,
        queued_at=datetime.now(UTC),
    )
    session.add(ticket)
    session.commit()

    response = client.post(f"/tickets/{ticket.id}/advance", json={"event": "mark_ready"})
    assert response.status_code == 409


def test_tickets_advance_404s_for_an_unknown_ticket(client: TestClient) -> None:
    response = client.post(f"/tickets/{uuid.uuid4()}/advance", json={"event": "start_prep"})
    assert response.status_code == 404
