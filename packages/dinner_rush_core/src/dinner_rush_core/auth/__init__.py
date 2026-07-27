"""RS256 JWT verification and JWKS handling (SPEC.md §6.3).

Gateway is the only signer — its private key never leaves it. Every other
service (kitchen, dispatch) is a verifier: it fetches gateway's public key
from `/.well-known/jwks.json`, caches it by `kid`, and checks signatures
against it. This module is the verifier side plus the one bit of encoding
(`build_jwk`) gateway reuses to publish its own key in the same shape a
verifier expects to parse.

Claims, per SPEC.md §6.3: `sub`, `role`, `scope[]`, `exp`, `correlation_id`.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from jwt.algorithms import RSAAlgorithm

_ALGORITHM = "RS256"


class TokenVerificationError(Exception):
    """The bearer token is missing, malformed, expired, or badly signed."""


@dataclass(frozen=True)
class Claims:
    sub: str
    role: str
    scope: list[str] = field(default_factory=list)
    exp: int = 0
    correlation_id: str | None = None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scope


def build_jwk(public_key: RSAPublicKey, kid: str) -> dict[str, object]:
    """Encode an RSA public key as a JWK — the shape both the publisher
    (gateway's `/.well-known/jwks.json`) and `JWKSClient` below agree on."""
    jwk: dict[str, object] = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = _ALGORITHM
    return jwk


class JWKSClient:
    """Fetches and caches a JWKS by `kid`.

    A cache miss on a known-good JWKS URL means the signer rotated its key —
    refetch once before giving up, rather than caching failure forever.
    """

    def __init__(
        self,
        jwks_url: str,
        *,
        timeout_seconds: float = 5.0,
        ttl_seconds: float = 300.0,
        fetch: Callable[[str, float], dict[str, object]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._jwks_url = jwks_url
        self._timeout_seconds = timeout_seconds
        self._ttl_seconds = ttl_seconds
        self._fetch = fetch or _http_fetch_jwks
        self._clock = clock
        self._keys_by_kid: dict[str, RSAPublicKey | RSAPrivateKey] = {}
        self._fetched_at: float | None = None

    def get_key(self, kid: str) -> RSAPublicKey | RSAPrivateKey:
        if kid not in self._keys_by_kid or self._is_stale():
            self._refresh()
        if kid not in self._keys_by_kid:
            raise TokenVerificationError(f"no JWKS key found for kid={kid!r}")
        return self._keys_by_kid[kid]

    def _is_stale(self) -> bool:
        return self._fetched_at is None or (self._clock() - self._fetched_at) > self._ttl_seconds

    def _refresh(self) -> None:
        try:
            body = self._fetch(self._jwks_url, self._timeout_seconds)
        except httpx.HTTPError as exc:
            raise TokenVerificationError(f"could not fetch JWKS from {self._jwks_url}") from exc

        raw_keys = body.get("keys", [])
        assert isinstance(raw_keys, list)
        keys: dict[str, RSAPublicKey | RSAPrivateKey] = {}
        for jwk in raw_keys:
            keys[jwk["kid"]] = RSAAlgorithm.from_jwk(jwk)
        self._keys_by_kid = keys
        self._fetched_at = self._clock()


def _http_fetch_jwks(url: str, timeout_seconds: float) -> dict[str, object]:
    response = httpx.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    body: dict[str, object] = response.json()
    return body


def verify_token(token: str, jwks_client: JWKSClient) -> Claims:
    """Verify signature + expiry against `jwks_client` and return the claims.

    Raises `TokenVerificationError` for any failure — bad signature, expired,
    missing `kid`, unknown `kid`, or a missing/invalid `role` claim. Callers
    map that to a 401.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise TokenVerificationError("malformed token") from exc

    kid = header.get("kid")
    if not kid:
        raise TokenVerificationError("token header is missing kid")

    key = jwks_client.get_key(kid)

    try:
        payload = jwt.decode(token, key=key, algorithms=[_ALGORITHM])  # type: ignore[arg-type]
    except jwt.PyJWTError as exc:
        raise TokenVerificationError(str(exc)) from exc

    role = payload.get("role")
    sub = payload.get("sub")
    if not role or not sub:
        raise TokenVerificationError("token is missing sub or role claims")

    return Claims(
        sub=sub,
        role=role,
        scope=list(payload.get("scope", [])),
        exp=int(payload.get("exp", 0)),
        correlation_id=payload.get("correlation_id"),
    )
