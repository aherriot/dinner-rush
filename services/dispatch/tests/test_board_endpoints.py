"""`GET /couriers` merging Postgres status with Redis position — the board's
dispatch panel needs both (SPEC.md §3.4)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dispatch.auth import get_claims
from dispatch.db import get_session
from dispatch.geo import set_position
from dispatch.main import app
from dispatch.models import Courier

_FULL_ACCESS_CLAIMS_KWARGS = {"sub": "gateway", "role": "service", "scope": ["dispatch:read"]}


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
