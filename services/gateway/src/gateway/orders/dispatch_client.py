"""Thin HTTP client for dispatch's board-read endpoints (SPEC.md §3.4).

Same shape as `kitchen_client.py` — explicit timeout, bounded retry with
jitter, a circuit breaker (ADR 0005), and a service token minted per call —
but a different failure direction. Kitchen's `get_capacity_quote` has a safe
fallback baked into the domain ("treat unreachable as at-capacity"); the
board's read of dispatch has no such fallback because there is nothing
unsafe about showing a stale or partial dispatch panel while gateway and
kitchen keep working — that degraded-but-honest board is Phase 8/10's whole
argument for Streams over pub/sub. So a failure here returns `None` rather
than synthesizing an empty list, letting `BoardSnapshotView` tell the
difference between "dispatch says there are no couriers" and "dispatch
didn't answer."
"""

import os
from functools import lru_cache

import httpx

from dinner_rush_core.config import load_config
from dinner_rush_core.resilience import CircuitBreaker, CircuitBreakerOpenError, retry_with_jitter
from gateway.common.service_tokens import mint_service_token

DISPATCH_BASE_URL = os.environ.get("DISPATCH_BASE_URL", "http://dispatch:8002")

_TRANSIENT_ERRORS: tuple[type[Exception], ...] = (httpx.ConnectError, httpx.TimeoutException)


@lru_cache(maxsize=1)
def _get_breaker() -> CircuitBreaker:
    cfg = load_config().service_client
    return CircuitBreaker(
        failure_threshold=cfg.circuit_breaker_failure_threshold,
        reset_timeout_seconds=cfg.circuit_breaker_reset_seconds,
    )


def _get(
    path: str, *, correlation_id: str | None, client: httpx.Client | None
) -> list[dict[str, object]] | None:
    cfg = load_config().service_client
    token = mint_service_token(scope=["dispatch:read"], correlation_id=correlation_id)
    http = client if client is not None else httpx

    def _request() -> httpx.Response:
        response = http.get(
            f"{DISPATCH_BASE_URL}{path}",
            timeout=cfg.timeout_seconds,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response

    try:
        response = _get_breaker().call(
            lambda: retry_with_jitter(
                _request,
                max_attempts=cfg.retry_max_attempts,
                base_delay_seconds=cfg.retry_base_delay_seconds,
                max_delay_seconds=cfg.retry_max_delay_seconds,
                retry_on=_TRANSIENT_ERRORS,
            ),
            retry_on=_TRANSIENT_ERRORS,
        )
    except (httpx.HTTPError, CircuitBreakerOpenError):
        return None

    body: list[dict[str, object]] = response.json()
    return body


def get_trips(
    *, correlation_id: str | None = None, client: httpx.Client | None = None
) -> list[dict[str, object]] | None:
    """`GET /trips` — active trips only (SPEC.md §3.4). `None` means
    dispatch didn't answer; production callers never pass `client` — it's an
    injection point for tests."""
    return _get("/trips", correlation_id=correlation_id, client=client)


def get_couriers(
    *, correlation_id: str | None = None, client: httpx.Client | None = None
) -> list[dict[str, object]] | None:
    """`GET /couriers` — status + last-known position (SPEC.md §3.4)."""
    return _get("/couriers", correlation_id=correlation_id, client=client)
