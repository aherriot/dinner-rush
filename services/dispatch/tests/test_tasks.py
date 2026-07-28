"""`assign_order`'s retry backoff (ADR 0007 §2 / dispatch's Celery-scheduled
work): a permanently-unassignable order used to reschedule itself at a flat
~`assignment_retry_seconds` cadence forever. At `SPEED=10` that is roughly a
1-second real-world retry — high enough, sustained across enough stuck
orders, to starve the Celery worker's promotion of *other* tasks' countdowns
(notably `arrive_at_pickup`/`arrive_at_dropoff` for trips that already have a
courier), so a courier already mid-trip never got its own timer to fire and
never returned to idle. The fix is capped exponential backoff on the retry
countdown, keyed off a new `attempt` counter threaded through the recursive
`apply_async` call.

These tests only exercise the backoff calculation and the `attempt`
threading in isolation — `attempt_assignment` and `assign_order.apply_async`
are monkeypatched so no real Celery worker or broker is involved. The
courier-contention/assignment behaviour itself is covered by
`test_assignment.py`.
"""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest

from dinner_rush_core.config import CourierSpeedConfig, DispatchConfig, GridConfig, RestaurantConfig
from dispatch import tasks

_DISPATCH_CONFIG = DispatchConfig(
    grid=GridConfig(width=100, height=100),
    restaurant=RestaurantConfig(x=50, y=50),
    courier_count=8,
    courier_speed_cells_per_minute=CourierSpeedConfig(bike=22, scooter=38),
    search_radius_cells=30,
    max_trips_per_courier=2,
    batch_max_detour_cells=8,
    assignment_retry_seconds=10,
    max_assignment_retry_seconds=40,
    address_grant_ttl_seconds=3600,
    eta_recalc_interval_seconds=30,
)


class _FakeRootConfig:
    """Stands in for `RootConfig` — `assign_order` only ever reads
    `load_config().dispatch`, so nothing else needs to be real here."""

    def __init__(self, dispatch: DispatchConfig) -> None:
        self.dispatch = dispatch


@pytest.fixture
def unassignable(monkeypatch: pytest.MonkeyPatch) -> Callable[[], dict[str, Any]]:
    """Wires `assign_order` so `attempt_assignment` always reports "no
    courier available" and captures the resulting `apply_async` call instead
    of actually rescheduling — returns a getter for that call's kwargs."""
    monkeypatch.setattr(tasks, "load_config", lambda: _FakeRootConfig(_DISPATCH_CONFIG))
    monkeypatch.setattr(tasks, "_speed", lambda: 2)
    monkeypatch.setattr(tasks, "get_redis_client", lambda: None)
    monkeypatch.setattr(tasks, "attempt_assignment", lambda *args, **kwargs: None)

    captured: dict[str, Any] = {}

    def _fake_apply_async(*, args: tuple[object, ...], countdown: float) -> None:
        captured["args"] = args
        captured["countdown"] = countdown

    monkeypatch.setattr(tasks.assign_order, "apply_async", _fake_apply_async)

    def _get() -> dict[str, Any]:
        return captured

    return _get


def _run(attempt: int) -> None:
    tasks.assign_order(
        str(uuid4()),
        "4471",
        60,
        40,
        "1 Test Street",
        1,
        None,
        attempt,
    )


def test_first_retry_uses_the_base_assignment_retry_seconds(
    unassignable: Callable[[], dict[str, Any]],
) -> None:
    _run(attempt=0)
    call = unassignable()

    # base=10, speed=2 -> 5.0s; unchanged from the pre-backoff behaviour, so
    # the common case (a courier frees up within the first few seconds)
    # retries just as promptly as before.
    assert call["countdown"] == pytest.approx(5.0)
    assert call["args"][-1] == 1


def test_countdown_doubles_each_successive_attempt_below_the_cap(
    unassignable: Callable[[], dict[str, Any]],
) -> None:
    _run(attempt=1)
    assert unassignable()["countdown"] == pytest.approx(10.0)  # min(10*2, 40)/2

    _run(attempt=2)
    assert unassignable()["countdown"] == pytest.approx(20.0)  # min(10*4, 40)/2


def test_countdown_is_capped_at_max_assignment_retry_seconds(
    unassignable: Callable[[], dict[str, Any]],
) -> None:
    _run(attempt=3)
    # Uncapped this would be 10*2**3=80, but max_assignment_retry_seconds=40
    # caps it at 40/2=20.0 — not unbounded growth.
    assert unassignable()["countdown"] == pytest.approx(20.0)

    _run(attempt=10)
    # Far past the cap: still 20.0, not some enormous multiplied value.
    assert unassignable()["countdown"] == pytest.approx(20.0)


def test_attempt_counter_increments_by_one_on_each_reschedule(
    unassignable: Callable[[], dict[str, Any]],
) -> None:
    _run(attempt=4)
    assert unassignable()["args"][-1] == 5
