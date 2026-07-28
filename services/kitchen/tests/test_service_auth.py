import time
import uuid
from collections.abc import Iterator

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import kitchen.auth as auth_module
from dinner_rush_core.auth import JWKSClient, build_jwk
from kitchen.db import get_session
from kitchen.main import app

KID = "kitchen-test-kid"


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
        auth_module, "_jwks_client", JWKSClient("http://gateway/jwks", fetch=fetch)
    )
    app.dependency_overrides[get_session] = lambda: session
    test_client = TestClient(app)
    test_client.signing_key = private_key  # type: ignore[attr-defined]
    yield test_client
    app.dependency_overrides.clear()


def _signing_key(client: TestClient) -> rsa.RSAPrivateKey:
    return client.signing_key  # type: ignore[no-any-return,attr-defined]


def test_capacity_quote_401s_without_a_bearer_token(client: TestClient) -> None:
    response = client.post("/capacity/quote", json={"items": []})
    assert response.status_code == 401


def test_capacity_quote_401s_with_a_badly_signed_token(client: TestClient) -> None:
    other_private_key, _other_public = _keypair()
    token = _token(other_private_key, sub="gateway", role="service", scope=["kitchen:call"])

    response = client.post(
        "/capacity/quote", json={"items": []}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_capacity_quote_403s_without_the_kitchen_call_scope(client: TestClient) -> None:
    token = _token(_signing_key(client), sub="gateway", role="service", scope=["kitchen:read"])

    response = client.post(
        "/capacity/quote", json={"items": []}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_capacity_quote_403s_for_a_non_service_role(client: TestClient) -> None:
    token = _token(_signing_key(client), sub="manager-1", role="manager", scope=["kitchen:call"])

    response = client.post(
        "/capacity/quote", json={"items": []}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_capacity_quote_200s_with_a_correctly_scoped_service_token(client: TestClient) -> None:
    token = _token(_signing_key(client), sub="gateway", role="service", scope=["kitchen:call"])

    response = client.post(
        "/capacity/quote", json={"items": []}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


def test_queue_403s_for_a_capacity_only_scope(client: TestClient) -> None:
    token = _token(_signing_key(client), sub="gateway", role="service", scope=["kitchen:call"])

    response = client.get("/queue", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_healthz_needs_no_token(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200


def test_oven_status_403s_without_the_kitchen_advance_scope(client: TestClient) -> None:
    token = _token(_signing_key(client), sub="gateway", role="service", scope=["kitchen:read"])

    response = client.post(
        f"/ovens/{uuid.uuid4()}/status",
        json={"status": "down"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_oven_status_403s_for_a_non_service_role(client: TestClient) -> None:
    token = _token(
        _signing_key(client), sub="manager-1", role="manager", scope=["kitchen:advance"]
    )

    response = client.post(
        f"/ovens/{uuid.uuid4()}/status",
        json={"status": "down"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_oven_status_404s_with_a_correctly_scoped_service_token(client: TestClient) -> None:
    token = _token(_signing_key(client), sub="gateway", role="service", scope=["kitchen:advance"])

    response = client.post(
        f"/ovens/{uuid.uuid4()}/status",
        json={"status": "down"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # 404 (unknown oven), not 403 — proves the scope check passed.
    assert response.status_code == 404
