import jwt
import pytest
from django.contrib.auth.models import User
from django.test import Client

from dinner_rush_core.auth import JWKSClient, verify_token
from front_of_house.accounts.models import Staff
from front_of_house.accounts.views import ROLE_SCOPES
from front_of_house.common.keys import get_kid, get_public_key_pem
from front_of_house.common.service_tokens import mint_service_token
from front_of_house.customers.models import Customer


def _jwks_client_from_endpoint() -> JWKSClient:
    body = Client().get("/.well-known/jwks.json").json()

    def fetch(_url: str, _timeout: float) -> dict[str, object]:
        return body  # type: ignore[no-any-return]

    return JWKSClient("http://front-of-house/.well-known/jwks.json", fetch=fetch)


def _decode_user_token(token: str) -> dict[str, object]:
    """Customer/staff tokens are minted by simplejwt, not `mint_service_token`
    — simplejwt has no `kid` header support, so kitchen doesn't verify these
    via JWKS this phase (only the internal service token, below, does). Board
    calling kitchen directly with a staff token is a Phase 8 concern. Decode
    directly against the published public key here, same as front-of-house's own
    `JWTRoleAuthentication` does."""
    return jwt.decode(token, get_public_key_pem(), algorithms=["RS256"])


def test_jwks_endpoint_publishes_the_signing_keys_kid() -> None:
    response = Client().get("/.well-known/jwks.json")
    assert response.status_code == 200
    [key] = response.json()["keys"]
    assert key["kid"] == get_kid()
    assert key["alg"] == "RS256"
    assert key["use"] == "sig"


@pytest.mark.django_db
def test_customer_token_carries_sub_role_and_scope() -> None:
    customer = Customer.objects.create(name="Ada", email="ada@example.com", phone="555-0100")
    response = Client().post("/api/v1/auth/token", {"email": customer.email})
    assert response.status_code == 200

    payload = _decode_user_token(response.json()["access"])
    assert payload["role"] == "customer"
    assert payload["sub"] == str(customer.id)
    assert payload["scope"] == ROLE_SCOPES["customer"]


@pytest.mark.django_db
def test_staff_token_carries_manager_scope() -> None:
    user = User.objects.create_user(username="manny", password="pw")
    Staff.objects.create(name="Manny", role="manager", user=user)

    response = Client().post("/api/v1/auth/token", {"username": "manny", "password": "pw"})
    assert response.status_code == 200

    payload = _decode_user_token(response.json()["access"])
    assert payload["role"] == "manager"
    assert payload["scope"] == ROLE_SCOPES["manager"]


def test_mint_service_token_verifies_against_the_published_jwks() -> None:
    token = mint_service_token(scope=["kitchen:call"], correlation_id="corr-abc")

    claims = verify_token(token, _jwks_client_from_endpoint())

    assert claims.role == "service"
    assert claims.sub == "front_of_house"
    assert claims.scope == ["kitchen:call"]
    assert claims.correlation_id == "corr-abc"
