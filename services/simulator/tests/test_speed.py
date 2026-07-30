"""`SpeedTracker` — in particular `refresh()`, the piece `runner.run` now
awaits once, blocking, before the arrivals loop starts (see
`test_runner.py`'s `test_the_first_arrival_already_uses_the_speed_set_before_the_run_started`
for the end-to-end regression test this unit covers the primitive for).
"""

import asyncio
from collections.abc import Callable

import httpx
import pytest

from simulator.client.api import FrontOfHouseError
from simulator.speed import SpeedTracker


class _FakeClient:
    def __init__(self, *, speed: int = 5, error: Exception | None = None) -> None:
        self._speed = speed
        self._error = error
        self.calls = 0

    async def get_speed(self) -> int:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._speed


async def test_refresh_updates_current_from_the_client() -> None:
    tracker = SpeedTracker(_FakeClient(speed=10))  # type: ignore[arg-type]
    assert tracker.current == 1  # the default, before any fetch

    await tracker.refresh()

    assert tracker.current == 10


@pytest.mark.parametrize(
    "error", [FrontOfHouseError(503, "unavailable"), httpx.ConnectError("down")]
)
async def test_refresh_keeps_the_last_known_value_on_a_front_of_house_error(
    error: Exception,
) -> None:
    client = _FakeClient(error=error)
    tracker = SpeedTracker(client, initial=7)  # type: ignore[arg-type]

    await tracker.refresh()

    assert tracker.current == 7
    assert client.calls == 1


async def test_run_forever_refreshes_immediately_not_after_the_first_poll_interval() -> None:
    """`run_forever` polls-then-sleeps, not sleeps-then-polls — a long
    `poll_interval_seconds` must not delay the first fetch."""
    client = _FakeClient(speed=42)
    tracker = SpeedTracker(client, poll_interval_seconds=3600)  # type: ignore[arg-type]

    task = asyncio.create_task(tracker.run_forever())
    try:
        await asyncio.wait_for(_until(lambda: tracker.current == 42), timeout=1.0)
    finally:
        task.cancel()

    assert tracker.current == 42


async def _until(condition: Callable[[], bool]) -> None:
    while not condition():
        await asyncio.sleep(0)
