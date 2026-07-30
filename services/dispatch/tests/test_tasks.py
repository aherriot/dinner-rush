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

import os
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
import redis
from sqlalchemy.orm import Session

from dinner_rush_core.config import CourierSpeedConfig, DispatchConfig, GridConfig, RestaurantConfig
from dispatch import tasks
from dispatch.geo import get_position, set_position
from dispatch.models import Courier, Trip

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


@pytest.fixture
def redis_client() -> Iterator[redis.Redis]:
    client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    yield client
    client.delete("couriers:live")
    client.close()


def test_pickup_leg_countdown_shrinks_with_speed_not_grows(
    session: Session,
    redis_client: redis.Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`assign_order` used to compute `cells_per_second` as
    `speed_cells_per_min / 60 / speed` and then divide distance by *that* —
    equivalent to multiplying the wall-clock countdown by `speed` instead of
    dividing it, so a sped-up demo made couriers take *longer* to reach the
    restaurant, not shorter. `arrive_at_pickup`'s countdown must shrink as
    `speed` grows, matching `assignment.attempt_assignment`'s own
    `eta_seconds = distance_cells / _speed_cells_per_second(courier) / speed`
    (assignment.py:188) exactly."""
    courier = Courier(
        name="Test Courier",
        status="idle",
        vehicle="bike",
        speed_cells_per_min=60,  # 1 cell/domain-second, for round numbers
        shift_started_at=datetime.now(UTC),
    )
    session.add(courier)
    session.flush()
    set_position(redis_client, str(courier.id), 40, 50)  # 10 cells from the restaurant
    session.commit()

    monkeypatch.setattr(
        tasks,
        "load_config",
        lambda: _FakeRootConfig(_DISPATCH_CONFIG),
    )
    monkeypatch.setattr(tasks, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(tasks, "SessionLocal", lambda: session)
    monkeypatch.setattr(session, "close", lambda: None)  # fixture owns teardown
    monkeypatch.setattr(tasks, "_speed", lambda: 10)

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        tasks._tick_motion, "apply_async", lambda args: captured.setdefault("tick_args", args)
    )
    monkeypatch.setattr(
        tasks.arrive_at_pickup,
        "apply_async",
        lambda args, countdown: captured.update(pickup_args=args, pickup_countdown=countdown),
    )

    tasks.assign_order(str(uuid.uuid4()), "4471", 60, 40, "1 Test Street", 1, None, 0)

    # Domain duration is 10 cells / 1 cell-per-second = 10 domain-seconds;
    # at speed=10 that's 1.0 wall-clock second — not 10 * 10 = 100.
    assert captured["pickup_countdown"] == pytest.approx(1.0)
    # duration_seconds passed to the autopilot
    assert captured["tick_args"][-1] == pytest.approx(1.0)


def test_tick_motion_leaves_position_untouched_on_its_final_scheduled_tick(
    redis_client: redis.Redis,
) -> None:
    """`_tick_motion`'s last invocation is scheduled to land at the same
    instant as the paired `arrive_at_pickup`/`arrive_at_dropoff` task, with no
    guarantee which runs first. It used to write `(to_x, to_y)`
    unconditionally before checking `fraction >= 1.0`, so a courier
    `arrive_at_dropoff` had already released to idle and snapped back to the
    restaurant got silently dragged back to the old dropoff whenever this
    task lost that race — stranding it there until its next trip. The final
    tick must be a no-op so the arrival task is the sole writer of the leg's
    terminal position."""
    courier_id = str(uuid.uuid4())
    set_position(redis_client, courier_id, 50, 50)  # arrive_at_dropoff already snapped to base

    # This leg ran from the restaurant (50, 50) to a dropoff at (80, 20);
    # its own final tick landing after arrive_at_dropoff must not drag the
    # courier back to that dropoff.
    tasks._tick_motion(courier_id, 50, 50, 80, 20, datetime.now(UTC).isoformat(), 0.0)

    assert get_position(redis_client, courier_id) == (50, 50)


def test_arrive_at_pickup_snaps_courier_position_to_the_restaurant(
    session: Session,
    redis_client: redis.Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pickup leg's terminal position used to be written only by
    `_tick_motion`'s final tick, which is no longer guaranteed to run (see
    the test above) — `arrive_at_pickup` must write it explicitly instead,
    since every pickup is at the fixed restaurant point."""
    courier = Courier(
        name="Test Courier",
        status="assigned",
        vehicle="bike",
        speed_cells_per_min=60,
        shift_started_at=datetime.now(UTC),
    )
    session.add(courier)
    session.flush()
    set_position(redis_client, str(courier.id), 40, 50)  # still en route to pickup

    now = datetime.now(UTC)
    trip = Trip(
        courier_id=courier.id,
        order_id=uuid.uuid4(),
        code="4471",
        status="assigned",
        pickup_x=50,
        pickup_y=50,
        dropoff_x=80,
        dropoff_y=20,
        assigned_at=now,
        eta_at=now,
        distance_cells=10,
    )
    session.add(trip)
    session.commit()

    monkeypatch.setattr(tasks, "SessionLocal", lambda: session)
    monkeypatch.setattr(session, "close", lambda: None)  # fixture owns teardown
    monkeypatch.setattr(tasks, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(tasks._tick_motion, "apply_async", lambda args: None)
    monkeypatch.setattr(tasks.arrive_at_dropoff, "apply_async", lambda args, countdown: None)

    tasks.arrive_at_pickup(str(trip.id), 1, None)

    assert get_position(redis_client, str(courier.id)) == (50, 50)
