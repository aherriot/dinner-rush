"""SPEC.md §6.2 — the four temporal cases the address grant must pass.
This is the one test file PHASES.md Phase 7 calls out by name."""

import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import dispatch.auth as auth_module
from dinner_rush_core.auth import JWKSClient, build_jwk
from dispatch.db import get_session
from dispatch.main import app
from dispatch.models import AddressGrant, Courier, Trip

KID = "dispatch-test-kid"


def _keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _token(private_key: rsa.RSAPrivateKey, **claims: object) -> str:
    payload = {"iat": int(time.time()), "exp": int(time.time()) + 60, **claims}
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    private_key, public_key = _keypair()
    jwks_body = {"keys": [build_jwk(public_key, KID)]}

    def fetch(_url: str, _timeout: float) -> dict[str, object]:
        return jwks_body

    monkeypatch.setattr(
        auth_module, "_jwks_client", JWKSClient("http://front-of-house/jwks", fetch=fetch)
    )
    app.dependency_overrides[get_session] = lambda: session
    test_client = TestClient(app)
    test_client.signing_key = private_key  # type: ignore[attr-defined]
    yield test_client
    app.dependency_overrides.clear()


def _signing_key(client: TestClient) -> rsa.RSAPrivateKey:
    return client.signing_key  # type: ignore[no-any-return,attr-defined]


def _courier_token(client: TestClient, courier_id: uuid.UUID) -> str:
    return _token(
        _signing_key(client), sub=str(courier_id), role="courier", scope=["courier:own"]
    )


def _make_trip_with_grant(
    session: Session,
    *,
    granted_offset: timedelta = timedelta(seconds=0),
    expires_offset: timedelta = timedelta(hours=1),
    revoked: bool = False,
) -> tuple[Courier, Trip, AddressGrant]:
    now = datetime.now(UTC)
    courier = Courier(
        name="Test Courier", status="delivering", vehicle="bike", speed_cells_per_min=20
    )
    session.add(courier)
    session.flush()
    trip = Trip(
        courier_id=courier.id,
        order_id=uuid.uuid4(),
        code="4471",
        status="picked_up",
        pickup_x=50,
        pickup_y=50,
        dropoff_x=60,
        dropoff_y=40,
        assigned_at=now,
        eta_at=now + timedelta(minutes=10),
        distance_cells=14,
    )
    session.add(trip)
    session.flush()
    grant = AddressGrant(
        trip_id=trip.id,
        courier_id=courier.id,
        dropoff_x=60,
        dropoff_y=40,
        line1="1 Test Street",
        granted_at=now + granted_offset,
        expires_at=now + expires_offset,
        revoked_at=now if revoked else None,
    )
    session.add(grant)
    session.commit()
    return courier, trip, grant


def test_dropoff_403s_before_any_grant_exists(client: TestClient, session: Session) -> None:
    """Case 1 — before assignment: no grant row at all."""
    courier = Courier(name="No Grant Yet", status="idle", vehicle="bike", speed_cells_per_min=20)
    session.add(courier)
    session.flush()
    trip = Trip(
        courier_id=courier.id,
        order_id=uuid.uuid4(),
        code="9999",
        status="assigned",
        pickup_x=50,
        pickup_y=50,
        dropoff_x=51,
        dropoff_y=51,
        assigned_at=datetime.now(UTC),
        eta_at=datetime.now(UTC) + timedelta(minutes=5),
        distance_cells=1,
    )
    session.add(trip)
    session.commit()

    token = _courier_token(client, courier.id)
    response = client.get(
        f"/trips/{trip.id}/dropoff", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_dropoff_200s_during_a_live_grant(client: TestClient, session: Session) -> None:
    """Case 2 — during assignment: live grant, correct address."""
    courier, trip, _grant = _make_trip_with_grant(session)
    token = _courier_token(client, courier.id)

    response = client.get(
        f"/trips/{trip.id}/dropoff", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["line1"] == "1 Test Street"
    assert body["dropoff_x"] == 60
    assert body["dropoff_y"] == 40


def test_dropoff_403s_after_delivery_revokes_the_grant(
    client: TestClient, session: Session
) -> None:
    """Case 3 — after delivery: the grant was revoked."""
    courier, trip, _grant = _make_trip_with_grant(session, revoked=True)
    token = _courier_token(client, courier.id)

    response = client.get(
        f"/trips/{trip.id}/dropoff", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_dropoff_403s_after_expiry_even_if_the_trip_is_still_open(
    client: TestClient, session: Session
) -> None:
    """Case 4 — the one people forget: expired but never revoked, trip
    still open. Proves the grant is time-boxed, not merely lifecycle-boxed."""
    courier, trip, _grant = _make_trip_with_grant(
        session,
        granted_offset=timedelta(hours=-2),
        expires_offset=timedelta(hours=-1),
    )
    token = _courier_token(client, courier.id)

    response = client.get(
        f"/trips/{trip.id}/dropoff", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_dropoff_403s_for_a_different_couriers_token(client: TestClient, session: Session) -> None:
    """The grant is scoped to the assigned courier — another courier's own
    valid token must not read it."""
    _courier, trip, _grant = _make_trip_with_grant(session)
    other_courier = Courier(
        name="Someone Else", status="idle", vehicle="bike", speed_cells_per_min=20
    )
    session.add(other_courier)
    session.commit()

    token = _courier_token(client, other_courier.id)
    response = client.get(
        f"/trips/{trip.id}/dropoff", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_dropoff_401s_without_a_bearer_token(client: TestClient, session: Session) -> None:
    _courier, trip, _grant = _make_trip_with_grant(session)
    response = client.get(f"/trips/{trip.id}/dropoff")
    assert response.status_code == 401
