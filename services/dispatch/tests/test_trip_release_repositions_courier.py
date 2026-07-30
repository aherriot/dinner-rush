"""A courier released to idle by `deliver_trip`/`fail_trip` (the manual,
courier-client-facing endpoints in `dispatch.routers.trips`) must land back
at the restaurant, exactly like `dispatch.tasks.arrive_at_dropoff`'s
autopilot already does — the two are callers of the same state machine
(ADR 0007 §6), and `attempt_assignment`'s `GEOSEARCH` only ever looks for an
idle courier within `search_radius_cells` of the restaurant. Before this fix,
`_release_courier_if_idle` set the courier's status but never repositioned
it, so a courier released here (as opposed to via the autopilot) was
stranded wherever the trip ended, silently unfindable by future assignments.
"""

import os
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import redis
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import dispatch.auth as auth_module
import dispatch.routers.trips as trips_module
from dinner_rush_core.auth import JWKSClient, build_jwk
from dinner_rush_core.config import CourierSpeedConfig, DispatchConfig, GridConfig, RestaurantConfig
from dispatch.db import get_session
from dispatch.geo import get_position, set_position
from dispatch.main import app
from dispatch.models import Courier, Trip

KID = "dispatch-test-kid"

_RESTAURANT = RestaurantConfig(x=50, y=50)
_DISPATCH_CONFIG = DispatchConfig(
    grid=GridConfig(width=100, height=100),
    restaurant=_RESTAURANT,
    courier_count=8,
    courier_speed_cells_per_minute=CourierSpeedConfig(bike=22, scooter=38),
    search_radius_cells=30,
    max_trips_per_courier=2,
    batch_max_detour_cells=8,
    assignment_retry_seconds=10,
    max_assignment_retry_seconds=40,
    address_grant_ttl_seconds=3600,
    eta_recalc_interval_seconds=30,
)


class _FakeRootConfig:
    """Stands in for `RootConfig` — `_release_courier_if_idle` only ever
    reads `load_config().dispatch.restaurant`, so nothing else needs to be
    real here (same shape `test_tasks.py` uses)."""

    def __init__(self, dispatch: DispatchConfig) -> None:
        self.dispatch = dispatch


@pytest.fixture(autouse=True)
def _fixed_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trips_module, "load_config", lambda: _FakeRootConfig(_DISPATCH_CONFIG))


def _keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _token(private_key: rsa.RSAPrivateKey, **claims: object) -> str:
    payload = {"iat": int(time.time()), "exp": int(time.time()) + 60, **claims}
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})


@pytest.fixture
def redis_client() -> Iterator[redis.Redis]:
    # Must match the app code's own `REDIS_URL` (conftest.py redirects the
    # default DB 0 to DB 15 for test isolation) — a hardcoded URL here would
    # silently read/write a different database than `get_redis_client()`.
    client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    yield client
    client.delete("couriers:live")
    client.close()


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    private_key, public_key = _keypair()
    jwks_body = {"keys": [build_jwk(public_key, KID)]}

    def fetch(_url: str, _timeout: float) -> dict[str, object]:
        return jwks_body

    monkeypatch.setattr(auth_module, "_jwks_client", JWKSClient("http://gateway/jwks", fetch=fetch))
    app.dependency_overrides[get_session] = lambda: session
    test_client = TestClient(app)
    test_client.signing_key = private_key  # type: ignore[attr-defined]
    yield test_client
    app.dependency_overrides.clear()


def _courier_token(client: TestClient, courier_id: uuid.UUID) -> str:
    return _token(
        client.signing_key,  # type: ignore[attr-defined]
        sub=str(courier_id),
        role="courier",
        scope=["courier:own"],
    )


def _make_trip(
    session: Session, redis_client: redis.Redis, *, dropoff_x: int, dropoff_y: int
) -> tuple[Courier, Trip]:
    now = datetime.now(UTC)
    courier = Courier(
        name="Test Courier", status="delivering", vehicle="bike", speed_cells_per_min=20
    )
    session.add(courier)
    session.flush()
    # Wherever the courier last reported from — far from the restaurant, so
    # a passing test can't be an accident of already being at (50, 50).
    set_position(redis_client, str(courier.id), dropoff_x, dropoff_y)
    trip = Trip(
        courier_id=courier.id,
        order_id=uuid.uuid4(),
        code="4471",
        status="delivering",
        pickup_x=50,
        pickup_y=50,
        dropoff_x=dropoff_x,
        dropoff_y=dropoff_y,
        assigned_at=now,
        eta_at=now + timedelta(minutes=10),
        distance_cells=14,
    )
    session.add(trip)
    session.commit()
    return courier, trip


def test_delivering_a_couriers_only_trip_snaps_them_back_to_the_restaurant(
    client: TestClient, session: Session, redis_client: redis.Redis
) -> None:
    courier, trip = _make_trip(session, redis_client, dropoff_x=5, dropoff_y=90)
    token = _courier_token(client, courier.id)

    response = client.post(
        f"/trips/{trip.id}/deliver", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert get_position(redis_client, str(courier.id)) == (50, 50)
    session.refresh(courier)
    assert courier.status == "idle"


def test_failing_a_couriers_only_trip_snaps_them_back_to_the_restaurant(
    client: TestClient, session: Session, redis_client: redis.Redis
) -> None:
    courier, trip = _make_trip(session, redis_client, dropoff_x=95, dropoff_y=3)
    token = _courier_token(client, courier.id)

    response = client.post(
        f"/trips/{trip.id}/fail",
        json={"reason": "no_answer"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert get_position(redis_client, str(courier.id)) == (50, 50)
    session.refresh(courier)
    assert courier.status == "idle"


def test_delivering_one_of_two_active_trips_leaves_the_courier_at_the_dropoff(
    client: TestClient, session: Session, redis_client: redis.Redis
) -> None:
    """A courier still juggling another active trip must not be pulled back
    to base mid-batch — only their last active trip snaps them home."""
    courier, trip = _make_trip(session, redis_client, dropoff_x=20, dropoff_y=80)
    other_trip = Trip(
        courier_id=courier.id,
        order_id=uuid.uuid4(),
        code="4472",
        status="assigned",
        pickup_x=50,
        pickup_y=50,
        dropoff_x=60,
        dropoff_y=60,
        assigned_at=datetime.now(UTC),
        eta_at=datetime.now(UTC) + timedelta(minutes=10),
        distance_cells=14,
    )
    session.add(other_trip)
    session.commit()
    token = _courier_token(client, courier.id)

    response = client.post(
        f"/trips/{trip.id}/deliver", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert get_position(redis_client, str(courier.id)) == (20, 80)
    session.refresh(courier)
    assert courier.status == "delivering"
