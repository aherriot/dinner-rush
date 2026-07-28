"""SPEC.md §3.4/§5 — nearest-available assignment and the ETA/distance math.
Batching is covered lightly here; the address grant it produces has its own
file (`test_address_grant.py`)."""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
import redis
from sqlalchemy.orm import Session

from dinner_rush_core.config import CourierSpeedConfig, DispatchConfig, GridConfig, RestaurantConfig
from dispatch.assignment import attempt_assignment
from dispatch.geo import set_position
from dispatch.models import Courier

_CONFIG = DispatchConfig(
    grid=GridConfig(width=100, height=100),
    restaurant=RestaurantConfig(x=50, y=50),
    courier_count=8,
    courier_speed_cells_per_minute=CourierSpeedConfig(bike=22, scooter=38),
    search_radius_cells=30,
    max_trips_per_courier=2,
    batch_max_detour_cells=8,
    assignment_retry_seconds=10,
    address_grant_ttl_seconds=3600,
    eta_recalc_interval_seconds=30,
)


@pytest.fixture
def redis_client() -> Iterator[redis.Redis]:
    client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    yield client
    client.delete("couriers:live")
    client.close()


def _idle_courier(session: Session, redis_client: redis.Redis, *, x: int, y: int) -> Courier:
    courier = Courier(
        name=f"Courier at ({x},{y})",
        status="idle",
        vehicle="bike",
        speed_cells_per_min=22,
        shift_started_at=datetime.now(UTC),
    )
    session.add(courier)
    session.flush()
    set_position(redis_client, str(courier.id), x, y)
    return courier


def test_assigns_the_nearest_idle_courier_within_radius(
    session: Session, redis_client: redis.Redis
) -> None:
    far = _idle_courier(session, redis_client, x=90, y=90)
    near = _idle_courier(session, redis_client, x=52, y=51)
    session.commit()

    result = attempt_assignment(
        session,
        redis_client,
        order_id=uuid.uuid4(),
        code="4471",
        dropoff_x=60,
        dropoff_y=40,
        line1="1 Test Street",
        config=_CONFIG,
        speed=1,
    )

    assert result is not None
    assert result.courier_id == near.id
    assert result.courier_id != far.id


def test_returns_none_when_no_courier_is_idle_or_in_range(
    session: Session, redis_client: redis.Redis
) -> None:
    result = attempt_assignment(
        session,
        redis_client,
        order_id=uuid.uuid4(),
        code="4472",
        dropoff_x=60,
        dropoff_y=40,
        line1="1 Test Street",
        config=_CONFIG,
        speed=1,
    )

    assert result is None


def test_assignment_creates_a_live_address_grant(
    session: Session, redis_client: redis.Redis
) -> None:
    courier = _idle_courier(session, redis_client, x=51, y=51)
    session.commit()

    result = attempt_assignment(
        session,
        redis_client,
        order_id=uuid.uuid4(),
        code="4473",
        dropoff_x=60,
        dropoff_y=40,
        line1="42 Grid Avenue",
        config=_CONFIG,
        speed=1,
    )

    assert result is not None
    from dispatch.models import AddressGrant, Trip

    trip = session.get(Trip, result.trip_id)
    assert trip is not None
    assert trip.courier_id == courier.id
    assert trip.status == "assigned"

    grant = session.query(AddressGrant).filter_by(trip_id=trip.id).one()
    assert grant.line1 == "42 Grid Avenue"
    assert grant.revoked_at is None
    assert grant.expires_at > grant.granted_at
