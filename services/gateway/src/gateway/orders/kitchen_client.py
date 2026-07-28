"""Thin HTTP client for kitchen's capacity quote (SPEC.md §3.3).

Explicit timeout, bounded retry with jitter, and a circuit breaker (ADR 0005)
around every call, plus the service token that proves this call came from
gateway. None of the three change the failure direction that was already
correct before Phase 5: a kitchen that's slow, unreachable, or behind an open
breaker is treated as "at capacity" — refusing an order gateway can't confirm
kitchen can cook is the safe direction, not an error page.

Retry and the breaker only ever see connect/timeout failures — a 4xx from a
kitchen that answered (e.g. an unknown sku) is a real answer, not a transient
fault, and is never retried or counted against the breaker.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

import httpx

from dinner_rush_core.config import load_config
from dinner_rush_core.resilience import CircuitBreaker, CircuitBreakerOpenError, retry_with_jitter
from gateway.common.service_tokens import mint_service_token

KITCHEN_BASE_URL = os.environ.get("KITCHEN_BASE_URL", "http://kitchen:8001")

_TRANSIENT_ERRORS: tuple[type[Exception], ...] = (httpx.ConnectError, httpx.TimeoutException)


@lru_cache(maxsize=1)
def _get_breaker() -> CircuitBreaker:
    cfg = load_config().service_client
    return CircuitBreaker(
        failure_threshold=cfg.circuit_breaker_failure_threshold,
        reset_timeout_seconds=cfg.circuit_breaker_reset_seconds,
    )


@dataclass(frozen=True)
class CapacityQuote:
    can_accept: bool
    queue_depth: int
    projected_wait_s: float


def get_capacity_quote(
    items: list[dict[str, object]],
    *,
    correlation_id: str | None = None,
    client: httpx.Client | None = None,
) -> CapacityQuote:
    """`client` is an injection point for tests (e.g. an `httpx.Client` bound
    to kitchen's ASGI app instead of the real network) — production callers
    never pass it."""
    cfg = load_config().service_client
    token = mint_service_token(scope=["kitchen:call"], correlation_id=correlation_id)
    http = client if client is not None else httpx

    def _request() -> httpx.Response:
        response = http.post(
            f"{KITCHEN_BASE_URL}/capacity/quote",
            json={"items": items},
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
        return CapacityQuote(can_accept=False, queue_depth=0, projected_wait_s=0.0)

    body = response.json()
    return CapacityQuote(
        can_accept=body["can_accept"],
        queue_depth=body["queue_depth"],
        projected_wait_s=body["projected_wait_s"],
    )


class KitchenUnavailableError(Exception):
    """Raised only by writes (`set_oven_status`) — an admin action needs to
    know it didn't take effect. Reads (`get_queue`/`get_ovens`) instead
    return `None` on the same failures, since a degraded-but-honest board
    (kitchen's panel empty while orders keep flowing through gateway) is the
    whole point of Phase 8/10, not a reason to fail the request."""


def _get(
    path: str, *, correlation_id: str | None, client: httpx.Client | None
) -> list[dict[str, object]] | None:
    cfg = load_config().service_client
    token = mint_service_token(scope=["kitchen:read"], correlation_id=correlation_id)
    http = client if client is not None else httpx

    def _request() -> httpx.Response:
        response = http.get(
            f"{KITCHEN_BASE_URL}{path}",
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


def get_queue(
    *, correlation_id: str | None = None, client: httpx.Client | None = None
) -> list[dict[str, object]] | None:
    """`GET /queue` — tickets ordered by priority (SPEC.md §3.3). `None`
    means kitchen didn't answer; production callers never pass `client`."""
    return _get("/queue", correlation_id=correlation_id, client=client)


def get_ovens(
    *, correlation_id: str | None = None, client: httpx.Client | None = None
) -> list[dict[str, object]] | None:
    """`GET /ovens` — slot occupancy + `frees_at` (SPEC.md §3.3)."""
    return _get("/ovens", correlation_id=correlation_id, client=client)


def set_oven_status(
    oven_id: str,
    status: str,
    *,
    correlation_id: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, object]:
    """`POST /ovens/{id}/status` — the chaos "oven down" write path. Unlike
    the read functions above, a manager clicking this needs to know if it
    didn't take effect, so failure raises rather than degrading silently."""
    cfg = load_config().service_client
    token = mint_service_token(scope=["kitchen:advance"], correlation_id=correlation_id)
    http = client if client is not None else httpx

    def _request() -> httpx.Response:
        response = http.post(
            f"{KITCHEN_BASE_URL}/ovens/{oven_id}/status",
            json={"status": status},
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
    except httpx.HTTPStatusError:
        # Kitchen answered — a 404 (unknown oven) or 422 (bad status value)
        # is a real, well-formed answer the caller should see verbatim, not
        # a reachability failure.
        raise
    except (httpx.HTTPError, CircuitBreakerOpenError) as exc:
        raise KitchenUnavailableError(str(exc)) from exc

    result: dict[str, object] = response.json()
    return result
