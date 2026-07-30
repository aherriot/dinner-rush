"""SPEC.md §5 — deliberately simple.

`promised_at = accepted_at + projected_wait_s + drive_estimate_s + buffer_s`.
`projected_wait_s` now comes from kitchen's real `POST /capacity/quote`
(Phase 4). `drive_estimate_s` is `0` until Phase 7's dispatch can compute a
real one from courier speed and grid distance — dispatch doesn't exist yet,
so there is nothing to estimate a drive from. Durations are divided by
SPEED at the point of use, never stored pre-scaled.
"""

import datetime

from dinner_rush_core.config import FrontOfHouseConfig

DRIVE_ESTIMATE_SECONDS = 0  # Phase 7 replaces this with a real dispatch estimate


def subtotal_cents(items: list[tuple[int, int]]) -> int:
    """`items` is a list of (unit_price_cents, qty)."""
    return sum(unit_price_cents * qty for unit_price_cents, qty in items)


def delivery_fee_cents(subtotal: int, config: FrontOfHouseConfig) -> int:
    if subtotal >= config.free_delivery_threshold_cents:
        return 0
    return config.delivery_fee_cents


def total_cents(subtotal: int, delivery_fee: int) -> int:
    return subtotal + delivery_fee


def promised_at(
    accepted_at: datetime.datetime,
    speed: int,
    *,
    projected_wait_s: float,
    buffer_seconds: int,
) -> datetime.datetime:
    real_seconds = (projected_wait_s + DRIVE_ESTIMATE_SECONDS + buffer_seconds) / speed
    return accepted_at + datetime.timedelta(seconds=real_seconds)
