"""Verifies gateway-signed tokens on every non-health endpoint (SPEC.md §6.3).

Two kinds of caller this phase: `role == "service"` (gateway, scoped
per-call, minted by `gateway.common.service_tokens` — reserved for future
synchronous gateway->dispatch calls; nothing in this phase needs one, see
ADR 0007 §1) and `role == "courier"` (`scope=["courier:own"]`, `sub` is the
courier's own id). Gateway does not yet mint courier tokens (ADR 0007 §5) —
tests mint them directly the same way `kitchen/tests/test_service_auth.py`
does for service tokens, against dispatch's own JWKS-client mock.
"""

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException

from dinner_rush_core.auth import Claims, JWKSClient, TokenVerificationError, verify_token
from dispatch.settings import JWKS_URL

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
    """`dependencies=[Depends(require_service_scope("dispatch:call"))]` on a
    router — 403s unless the caller is gateway's service identity and its
    token was scoped to exactly this call."""

    def _check(claims: Claims = Depends(get_claims)) -> Claims:
        if claims.role != "service" or not claims.has_scope(scope):
            raise HTTPException(
                status_code=403, detail=f"token lacks required scope {scope!r} for role=service"
            )
        return claims

    return _check


def require_courier(claims: Claims = Depends(get_claims)) -> Claims:
    """Any authenticated courier — used where the path itself names which
    courier (`/couriers/{id}/...`) and the handler checks `claims.sub`
    against it, or where the token's own `sub` *is* the scope
    (`/couriers/me/trips`)."""
    if claims.role != "courier" or not claims.has_scope("courier:own"):
        raise HTTPException(status_code=403, detail="token lacks required role=courier")
    return claims
