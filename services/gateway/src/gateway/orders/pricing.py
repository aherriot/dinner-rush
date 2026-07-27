"""SPEC.md §5 — deliberately simple.

`promised_at` uses a fixed placeholder buffer in place of the real
`projected_wait_s` from `POST /capacity/quote`, which doesn't exist until the
kitchen service does (Phase 4). Durations are divided by SPEED at the point
of use, never stored pre-scaled.
"""

import datetime

from dinner_rush_core.config import GatewayConfig

# Stands in for kitchen.capacity.promise_buffer_seconds (config.example.yaml)
# until Phase 4's capacity quote replaces this estimate entirely.
PLACEHOLDER_PROMISE_SECONDS = 900


def subtotal_cents(items: list[tuple[int, int]]) -> int:
    """`items` is a list of (unit_price_cents, qty)."""
    return sum(unit_price_cents * qty for unit_price_cents, qty in items)


def delivery_fee_cents(subtotal: int, config: GatewayConfig) -> int:
    if subtotal >= config.free_delivery_threshold_cents:
        return 0
    return config.delivery_fee_cents


def total_cents(subtotal: int, delivery_fee: int) -> int:
    return subtotal + delivery_fee


def promised_at(accepted_at: datetime.datetime, speed: int) -> datetime.datetime:
    real_seconds = PLACEHOLDER_PROMISE_SECONDS / speed
    return accepted_at + datetime.timedelta(seconds=real_seconds)
