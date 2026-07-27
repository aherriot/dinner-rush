"""Verifies gateway-signed service tokens on every non-health endpoint.

Kitchen has exactly one caller this phase — gateway (SPEC.md §3.3's table
lists "gateway, board" for `/queue` and `/ovens`, but the board doesn't exist
until Phase 8, and it will need its own follow-up here since simplejwt's
customer/staff tokens carry no `kid` header — see ADR 0005). Until then every
endpoint requires `role == "service"` plus the specific scope that endpoint
needs, both minted per-call by `gateway.common.service_tokens`.
"""

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException

from dinner_rush_core.auth import Claims, JWKSClient, TokenVerificationError, verify_token
from kitchen.settings import JWKS_URL

_jwks_client = JWKSClient(JWKS_URL)


def get_claims(authorization: str | None = Header(default=None)) -> Claims:
    if authorization is None:
        raise HTTPException(status_code=401, detail="missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="expected 'Authorization: Bearer <token>'")

    try:
        return verify_token(token, _jwks_client)
    except TokenVerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_service_scope(scope: str) -> Callable[..., Claims]:
    """`dependencies=[Depends(require_service_scope("kitchen:call"))]` on a
    router — 403s unless the caller is gateway's service identity and its
    token was scoped to exactly this call."""

    def _check(claims: Claims = Depends(get_claims)) -> Claims:
        if claims.role != "service" or not claims.has_scope(scope):
            raise HTTPException(
                status_code=403, detail=f"token lacks required scope {scope!r} for role=service"
            )
        return claims

    return _check
