"""Going back online after `handle_courier_offline` (`dispatch.tasks`, the
`courier_offline` chaos scenario) must snap an idle courier back to the
restaurant, exactly like `arrive_at_dropoff` and
`routers.trips._release_courier_if_idle` already do for every other path
that releases a courier to idle — `attempt_assignment`'s `GEOSEARCH` only
ever looks within `search_radius_cells` of the restaurant, so a courier left
elsewhere is stranded until *something* repositions them. Before this fix,
`set_courier_status` flipped `offline -> idle` without touching position,
leaving a courier taken offline mid-trip idle wherever it was left.
"""

import os
import time
import uuid
from collections.abc import Iterator

import jwt
import pytest
import redis
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import dispatch.auth as auth_module
import dispatch.routers.couriers as couriers_module
from dinner_rush_core.auth import JWKSClient, build_jwk
from dinner_rush_core.config import CourierSpeedConfig, DispatchConfig, GridConfig, RestaurantConfig
from dispatch.db import get_session
from dispatch.geo import get_position, set_position
from dispatch.main import app
from dispatch.models import Courier

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
    """Stands in for `RootConfig` — `set_courier_status` only ever reads
    `load_config().dispatch.restaurant`, so nothing else needs to be real
    here (same shape `test_tasks.py` and
    `test_trip_release_repositions_courier.py` use)."""

    def __init__(self, dispatch: DispatchConfig) -> None:
        self.dispatch = dispatch


@pytest.fixture(autouse=True)
def _fixed_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(couriers_module, "load_config", lambda: _FakeRootConfig(_DISPATCH_CONFIG))


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


def test_going_online_after_offline_snaps_the_courier_back_to_the_restaurant(
    client: TestClient, session: Session, redis_client: redis.Redis
) -> None:
    courier = Courier(name="Test Courier", status="offline", vehicle="bike", speed_cells_per_min=20)
    session.add(courier)
    session.commit()
    # Wherever they were left when taken offline mid-trip — far from base,
    # so a passing test can't be an accident of already being at (50, 50).
    set_position(redis_client, str(courier.id), 12, 88)
    token = _courier_token(client, courier.id)

    response = client.post(
        f"/couriers/{courier.id}/status",
        json={"status": "online"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert get_position(redis_client, str(courier.id)) == (50, 50)
    session.refresh(courier)
    assert courier.status == "idle"


def test_going_online_while_already_idle_leaves_position_untouched(
    client: TestClient, session: Session, redis_client: redis.Redis
) -> None:
    """A courier that was never offline (e.g. an idempotent retry of the
    online call) shouldn't get yanked back to base for no reason."""
    courier = Courier(name="Test Courier", status="idle", vehicle="bike", speed_cells_per_min=20)
    session.add(courier)
    session.commit()
    set_position(redis_client, str(courier.id), 65, 50)
    token = _courier_token(client, courier.id)

    response = client.post(
        f"/couriers/{courier.id}/status",
        json={"status": "online"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert get_position(redis_client, str(courier.id)) == (65, 50)


def test_going_offline_does_not_move_the_courier(
    client: TestClient, session: Session, redis_client: redis.Redis
) -> None:
    """No active trip here on purpose — `handle_courier_offline` only has
    unassignment work to do (which schedules a real Celery reassignment task)
    when there's a trip to unassign; this test is solely about the position
    invariant for an already-idle courier going offline."""
    courier = Courier(name="Test Courier", status="idle", vehicle="bike", speed_cells_per_min=20)
    session.add(courier)
    session.commit()
    set_position(redis_client, str(courier.id), 30, 30)
    token = _courier_token(client, courier.id)

    response = client.post(
        f"/couriers/{courier.id}/status",
        json={"status": "offline"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert get_position(redis_client, str(courier.id)) == (30, 30)
    session.refresh(courier)
    assert courier.status == "offline"
