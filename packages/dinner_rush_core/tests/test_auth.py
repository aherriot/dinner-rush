import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from dinner_rush_core.auth import (
    Claims,
    JWKSClient,
    TokenVerificationError,
    build_jwk,
    verify_token,
)

KID = "test-key-1"


def _keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _sign(private_key: rsa.RSAPrivateKey, **claims: object) -> str:
    payload = {"iat": int(time.time()), "exp": int(time.time()) + 60, **claims}
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})


def _jwks_client_for(public_key: rsa.RSAPublicKey, *, calls: list[int] | None = None) -> JWKSClient:
    jwks_body = {"keys": [build_jwk(public_key, KID)]}

    def fetch(_url: str, _timeout: float) -> dict[str, object]:
        if calls is not None:
            calls.append(1)
        return jwks_body

    return JWKSClient("http://gateway/.well-known/jwks.json", fetch=fetch)


def test_verify_token_round_trips_all_claims() -> None:
    private_key, public_key = _keypair()
    token = _sign(
        private_key,
        sub="gateway",
        role="service",
        scope=["kitchen:call"],
        correlation_id="corr-123",
    )

    claims = verify_token(token, _jwks_client_for(public_key))

    assert claims == Claims(
        sub="gateway",
        role="service",
        scope=["kitchen:call"],
        exp=claims.exp,
        correlation_id="corr-123",
    )
    assert claims.has_scope("kitchen:call")
    assert not claims.has_scope("admin:all")


def test_verify_token_rejects_a_signature_from_the_wrong_key() -> None:
    _private_key, public_key = _keypair()
    other_private_key, _other_public_key = _keypair()
    forged = _sign(other_private_key, sub="gateway", role="service", scope=[])

    with pytest.raises(TokenVerificationError):
        verify_token(forged, _jwks_client_for(public_key))


def test_verify_token_rejects_an_expired_token() -> None:
    private_key, public_key = _keypair()
    expired = jwt.encode(
        {"sub": "gateway", "role": "service", "scope": [], "exp": int(time.time()) - 10},
        private_key,
        algorithm="RS256",
        headers={"kid": KID},
    )

    with pytest.raises(TokenVerificationError):
        verify_token(expired, _jwks_client_for(public_key))


def test_verify_token_rejects_a_token_missing_role() -> None:
    private_key, public_key = _keypair()
    token = _sign(private_key, sub="gateway", scope=[])

    with pytest.raises(TokenVerificationError):
        verify_token(token, _jwks_client_for(public_key))


def test_verify_token_rejects_an_unknown_kid() -> None:
    private_key, public_key = _keypair()
    token = jwt.encode(
        {"sub": "gateway", "role": "service", "scope": [], "exp": int(time.time()) + 60},
        private_key,
        algorithm="RS256",
        headers={"kid": "some-other-kid"},
    )

    with pytest.raises(TokenVerificationError):
        verify_token(token, _jwks_client_for(public_key))


def test_jwks_client_caches_and_only_refetches_once_per_unknown_kid() -> None:
    _private_key, public_key = _keypair()
    calls: list[int] = []
    client = _jwks_client_for(public_key, calls=calls)

    client.get_key(KID)
    client.get_key(KID)
    assert len(calls) == 1

    with pytest.raises(TokenVerificationError):
        client.get_key("nonexistent")
    # one extra fetch attempting to find the unknown kid, then it gives up
    assert len(calls) == 2
