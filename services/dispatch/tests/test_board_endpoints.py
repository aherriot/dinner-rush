"""`GET /couriers` merging Postgres status with Redis position, and
`GET /backlog`'s `pending_dropoff`-with-no-`trip` count (SPEC.md §3.4)."""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dispatch.auth import get_claims
from dispatch.db import get_session
from dispatch.geo import set_position
from dispatch.main import app
from dispatch.models import Courier, PendingDropoff, Trip

_FULL_ACCESS_CLAIMS_KWARGS = {
    "sub": "front_of_house",
    "role": "service",
    "scope": ["dispatch:read"],
}


@pytest.fixture
def redis_client() -> Iterator[redis.Redis]:
    client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    yield client
    client.delete("couriers:live")
    client.close()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    from dinner_rush_core.auth import Claims

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_claims] = lambda: Claims(
        exp=0, correlation_id=None, **_FULL_ACCESS_CLAIMS_KWARGS
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_couriers_list_merges_redis_position_onto_postgres_status(
    session: Session, redis_client: redis.Redis, client: TestClient
) -> None:
    courier = Courier(
        name="Test Courier",
        status="idle",
        vehicle="bike",
        speed_cells_per_min=22,
        shift_started_at=datetime.now(UTC),
    )
    session.add(courier)
    session.commit()
    set_position(redis_client, str(courier.id), 42, 17)

    response = client.get("/couriers")
    assert response.status_code == 200
    [body] = response.json()
    assert body["status"] == "idle"
    assert body["x"] == 42
    assert body["y"] == 17


def test_couriers_list_reports_null_position_for_a_courier_that_never_reported(
    session: Session, client: TestClient
) -> None:
    courier = Courier(
        name="Never Reported",
        status="offline",
        vehicle="scooter",
        speed_cells_per_min=38,
        shift_started_at=None,
    )
    session.add(courier)
    session.commit()

    response = client.get("/couriers")
    assert response.status_code == 200
    [body] = response.json()
    assert body["x"] is None
    assert body["y"] is None


def _make_pending_dropoff(
    session: Session, *, created_at: datetime, ready_at: datetime | None = None
) -> PendingDropoff:
    pending = PendingDropoff(
        order_id=uuid.uuid4(),
        code=f"T{created_at.timestamp():.0f}",
        dropoff_x=10,
        dropoff_y=10,
        line1="1 Test St",
        created_at=created_at,
        ready_at=ready_at,
    )
    session.add(pending)
    return pending


def test_backlog_reports_zero_and_no_oldest_age_when_nothing_is_waiting(
    session: Session, client: TestClient
) -> None:
    response = client.get("/backlog")
    assert response.status_code == 200
    assert response.json() == {"ready_count": 0, "oldest_waiting_seconds": None}


def test_backlog_counts_pending_dropoffs_and_ages_the_oldest_by_when_it_went_ready(
    session: Session, client: TestClient
) -> None:
    now = datetime.now(UTC)
    # Placed long ago but only went `ready` 15 minutes ago — the backlog age
    # must come from `ready_at`, not `created_at`, or a slow-cooking order
    # would inflate the "how long has this been waiting on a courier" number.
    _make_pending_dropoff(
        session, created_at=now - timedelta(hours=2), ready_at=now - timedelta(minutes=15)
    )
    _make_pending_dropoff(session, created_at=now, ready_at=now - timedelta(minutes=2))
    session.commit()

    response = client.get("/backlog")
    assert response.status_code == 200
    body = response.json()
    assert body["ready_count"] == 2
    # ~15 minutes old, generous bounds so a slow CI box can't flake this.
    assert 14 * 60 < body["oldest_waiting_seconds"] < 16 * 60


def test_backlog_excludes_orders_still_cooking_with_no_ready_at_yet(
    session: Session, client: TestClient
) -> None:
    """A `pending_dropoff` row exists from `order.placed` onward (ADR 0007
    §1) — long before the kitchen has actually boxed the order. Only rows
    where `order.ready` has fired (`ready_at` set) belong in the backlog;
    otherwise "N ready" would count orders still queued/prepping/baking."""
    _make_pending_dropoff(session, created_at=datetime.now(UTC) - timedelta(minutes=10))
    session.commit()

    response = client.get("/backlog")
    assert response.status_code == 200
    assert response.json() == {"ready_count": 0, "oldest_waiting_seconds": None}


def test_backlog_excludes_an_order_that_already_has_a_trip(
    session: Session, client: TestClient
) -> None:
    """A `pending_dropoff` row is only ever deleted on a successful
    assignment (`dispatch.tasks.assign_order`) — this covers the defensive
    `NOT EXISTS` join rather than relying solely on that invariant."""
    courier = Courier(
        name="Assigned Courier", status="assigned", vehicle="bike", speed_cells_per_min=20
    )
    session.add(courier)
    session.flush()

    pending = _make_pending_dropoff(
        session,
        created_at=datetime.now(UTC) - timedelta(minutes=30),
        ready_at=datetime.now(UTC) - timedelta(minutes=30),
    )
    session.add(
        Trip(
            courier_id=courier.id,
            order_id=pending.order_id,
            code=pending.code,
            status="assigned",
            pickup_x=50,
            pickup_y=50,
            dropoff_x=10,
            dropoff_y=10,
            assigned_at=datetime.now(UTC),
            eta_at=datetime.now(UTC) + timedelta(minutes=5),
            distance_cells=40,
        )
    )
    session.commit()

    response = client.get("/backlog")
    assert response.status_code == 200
    assert response.json() == {"ready_count": 0, "oldest_waiting_seconds": None}
