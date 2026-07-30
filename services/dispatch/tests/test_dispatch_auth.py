import time
from collections.abc import Iterator

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import dispatch.auth as auth_module
from dinner_rush_core.auth import JWKSClient, build_jwk
from dispatch.db import get_session
from dispatch.main import app

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


def test_couriers_list_401s_without_a_bearer_token(client: TestClient) -> None:
    response = client.get("/couriers")
    assert response.status_code == 401


def test_couriers_list_403s_with_a_courier_role_instead_of_service(client: TestClient) -> None:
    token = _token(_signing_key(client), sub="courier-1", role="courier", scope=["courier:own"])
    response = client.get("/couriers", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_couriers_list_200s_with_the_dispatch_read_scope(client: TestClient) -> None:
    token = _token(
        _signing_key(client), sub="front_of_house", role="service", scope=["dispatch:read"]
    )
    response = client.get("/couriers", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_my_trips_403s_for_a_service_token(client: TestClient) -> None:
    token = _token(
        _signing_key(client), sub="front_of_house", role="service", scope=["dispatch:read"]
    )
    response = client.get("/couriers/me/trips", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_healthz_needs_no_token(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
