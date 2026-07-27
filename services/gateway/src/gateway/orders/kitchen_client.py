"""Thin HTTP client for kitchen's capacity quote (SPEC.md §3.3).

Explicit timeout, no retry, no circuit breaker — those are Phase 5's job
("every cross-service call gets an explicit timeout, bounded retry with
jitter, and a circuit breaker", PHASES.md Phase 5). Until then, a kitchen
that's slow or unreachable is treated as "at capacity" — refusing an order
gateway can't confirm kitchen can cook is the safe failure direction, not
an error page.
"""

import os
from dataclasses import dataclass

import httpx

KITCHEN_BASE_URL = os.environ.get("KITCHEN_BASE_URL", "http://kitchen:8001")
_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class CapacityQuote:
    can_accept: bool
    queue_depth: int
    projected_wait_s: float


def get_capacity_quote(items: list[dict[str, object]]) -> CapacityQuote:
    try:
        response = httpx.post(
            f"{KITCHEN_BASE_URL}/capacity/quote", json={"items": items}, timeout=_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        body = response.json()
    except httpx.HTTPError:
        return CapacityQuote(can_accept=False, queue_depth=0, projected_wait_s=0.0)
    return CapacityQuote(
        can_accept=body["can_accept"],
        queue_depth=body["queue_depth"],
        projected_wait_s=body["projected_wait_s"],
    )
