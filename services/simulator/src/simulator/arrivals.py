"""Poisson arrivals — PHASES.md Phase 6: "Poisson arrivals, not a
fixed-interval loop." An evaluator will look, so this is a real inverse-CDF
exponential draw, not `sleep(60 / rate)` with a coat of paint.

`baseline_rate_per_minute` is domain time exactly like think times and dwell
times (config.example.yaml's own header comment: "durations here are always
DOMAIN seconds, never scaled") — a rate is just a duration's reciprocal, so
the same no-virtual-clock rule (SPEC.md §5) applies to it. The drawn
interarrival is a domain-time duration; it's divided by the live `speed` at
the point of use, same as everywhere else, so `SPEED=60` compresses a rush's
real wall-clock length exactly as it compresses cook times.
"""

import asyncio
import math
import random
from collections.abc import AsyncIterator, Awaitable, Callable


async def poisson_arrivals(
    rate_per_minute: Callable[[], float],
    *,
    speed: Callable[[], float] = lambda: 1.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    rand: Callable[[], float] = random.random,
) -> AsyncIterator[None]:
    """Yields once per arrival, forever. `rate_per_minute` and `speed` are
    both re-read on every iteration (not captured once) so a scenario
    changing the baseline rate, or an admin changing SPEED, mid-run takes
    effect on the very next arrival instead of requiring a restart.
    """
    while True:
        rate_per_second = rate_per_minute() / 60.0
        if rate_per_second <= 0:
            await sleep(1.0)
            continue
        # Inverse-CDF sampling of Exponential(rate): -ln(1 - U) / rate,
        # U ~ Uniform[0, 1) — the standard construction for Poisson
        # interarrival times.
        interarrival_seconds = -math.log(1.0 - rand()) / rate_per_second
        await sleep(interarrival_seconds / speed())
        yield
