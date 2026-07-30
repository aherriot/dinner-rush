import asyncio

import pytest

from simulator.client.api import FrontOfHouseError
from simulator.scenario_overrides import ScenarioOverrideTracker


class _FakeClient:
    def __init__(self, overrides: dict[str, object] | Exception) -> None:
        self._overrides = overrides

    async def get_active_scenario_overrides(self) -> dict[str, object]:
        if isinstance(self._overrides, Exception):
            raise self._overrides
        return self._overrides


def test_current_rate_per_minute_falls_back_to_baseline_with_no_active_override() -> None:
    tracker = ScenarioOverrideTracker(_FakeClient({}))
    assert tracker.current_rate_per_minute(6.0) == 6.0


async def test_run_forever_applies_a_polled_rate_override() -> None:
    tracker = ScenarioOverrideTracker(
        _FakeClient({"simulator.customers.baseline_rate_per_minute": 18}),
        poll_interval_seconds=0.01,
    )
    task = asyncio.create_task(tracker.run_forever())
    try:
        for _ in range(200):
            if tracker.current_rate_per_minute(6.0) == 18.0:
                break
            await asyncio.sleep(0.005)
        assert tracker.current_rate_per_minute(6.0) == 18.0
    finally:
        task.cancel()


def test_current_basket_size_weights_falls_back_to_baseline_when_absent() -> None:
    tracker = ScenarioOverrideTracker(_FakeClient({}))
    baseline = {1: 0.5, 2: 0.5}
    assert tracker.current_basket_size_weights(baseline) == baseline


def test_current_basket_size_weights_applies_an_active_override() -> None:
    tracker = ScenarioOverrideTracker(_FakeClient({}))
    tracker._overrides = {  # type: ignore[attr-defined]
        "simulator.customers.basket_size_weights": {"1": 0.25, "2": 0.75}
    }
    assert tracker.current_basket_size_weights({1: 0.5, 2: 0.5}) == {1: 0.25, 2: 0.75}


def test_ignores_overrides_this_process_has_no_consumer_for() -> None:
    """`courier_offline`'s `simulator.couriers.spontaneous_offline_probability`
    has no code path reading it (dispatch's own autopilot drives couriers,
    not the simulator) — a tracker holding it must not surface it as either
    a rate or a basket-weight override."""
    tracker = ScenarioOverrideTracker(_FakeClient({}))
    tracker._overrides = {  # type: ignore[attr-defined]
        "simulator.couriers.spontaneous_offline_probability": 0.25
    }
    assert tracker.current_rate_per_minute(6.0) == 6.0
    assert tracker.current_basket_size_weights({1: 1.0}) == {1: 1.0}


async def test_a_front_of_house_error_does_not_crash_the_poll_loop() -> None:
    tracker = ScenarioOverrideTracker(
        _FakeClient(FrontOfHouseError(503, "unavailable")), poll_interval_seconds=0.01
    )
    task = asyncio.create_task(tracker.run_forever())
    await asyncio.sleep(0.05)
    assert not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
