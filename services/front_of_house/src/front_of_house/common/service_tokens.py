"""Service-to-service tokens front-of-house mints for its own outbound calls.

Distinct from `accounts.views._issue_token` (customer/staff login, verified by
front-of-house itself via `VERIFYING_KEY`): a service token is minted per outbound
call, verified by the *other* service via JWKS, `role="service"`, scoped to
exactly what that call needs, and short-lived — 30s is generous for a
same-network HTTP round trip and deliberately too short to be worth stealing.

The `exp` here is a real wall-clock TTL for token freshness, not a simulated
domain duration — it is not divided by `SPEED` (SPEC.md §5's no-virtual-clock
rule governs simulated durations, not infrastructure token lifetimes).
"""

import time

import jwt

from front_of_house.common.keys import get_kid, get_private_key_pem

_ALGORITHM = "RS256"
_DEFAULT_TTL_SECONDS = 30


def mint_service_token(
    *, scope: list[str], correlation_id: str | None, ttl_seconds: int = _DEFAULT_TTL_SECONDS
) -> str:
    now = int(time.time())
    payload = {
        "sub": "front_of_house",
        "role": "service",
        "scope": scope,
        "iat": now,
        "exp": now + ttl_seconds,
        "correlation_id": correlation_id,
    }
    return jwt.encode(
        payload, get_private_key_pem(), algorithm=_ALGORITHM, headers={"kid": get_kid()}
    )
