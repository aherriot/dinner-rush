import math

import pytest

from simulator.arrivals import poisson_arrivals


async def test_yields_after_sleeping_the_inverse_cdf_interarrival_time() -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    rand_values = iter([0.5, 0.25])

    def fake_rand() -> float:
        return next(rand_values)

    gen = poisson_arrivals(lambda: 60.0, sleep=fake_sleep, rand=fake_rand)  # 1/second
    await anext(gen)
    await anext(gen)

    assert sleeps == [pytest.approx(-math.log(0.5)), pytest.approx(-math.log(0.75))]


async def test_a_zero_rate_stalls_without_yielding_until_the_rate_recovers() -> None:
    sleeps: list[float] = []
    rate = [0.0]

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        rate[0] = 60.0  # recovers after the first stall

    gen = poisson_arrivals(lambda: rate[0], sleep=fake_sleep, rand=lambda: 0.5)
    await anext(gen)

    assert sleeps[0] == 1.0
    assert len(sleeps) == 2  # the 1s stall, then the real interarrival sleep


async def test_the_rate_is_read_fresh_on_every_iteration() -> None:
    """A scenario overriding `baseline_rate_per_minute` mid-run must affect
    the very next arrival, not just arrivals spawned after a restart."""
    rate = [60.0]
    seen_rates: list[float] = []

    async def fake_sleep(_seconds: float) -> None:
        return None

    def fake_rand() -> float:
        return 0.5

    gen = poisson_arrivals(lambda: rate[0], sleep=fake_sleep, rand=fake_rand)
    await anext(gen)
    seen_rates.append(rate[0])
    rate[0] = 600.0
    await anext(gen)
    seen_rates.append(rate[0])

    assert seen_rates == [60.0, 600.0]


async def test_a_higher_speed_shrinks_the_real_sleep_by_the_same_factor() -> None:
    """SPEC.md §5's no-virtual-clock rule: the interarrival draw is a
    domain-time duration like any other, so `SPEED=60` must compress the
    real wall-clock wait exactly as it compresses cook times."""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    gen = poisson_arrivals(
        lambda: 60.0, speed=lambda: 60.0, sleep=fake_sleep, rand=lambda: 0.5
    )
    await anext(gen)

    assert sleeps[0] == pytest.approx(-math.log(0.5) / 60.0)
