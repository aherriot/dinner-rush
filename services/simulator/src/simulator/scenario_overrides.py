"""Polls front-of-house's `GET /scenarios/active` (SPEC.md §3.2, PHASES.md Phase 8)
so a manager clicking "Friday rush" on the board changes a *running*
simulator's behaviour, not just the `--scenario` CLI flag's one-shot patch
at process startup (`config.apply_scenario_overrides`). Same shape as
`speed.py`'s `SpeedTracker`: front-of-house owns the truth in Redis, this ordinary
API client only polls a public endpoint for it, since it has no service
credentials to read Redis directly (CLAUDE.md §5).

Only overrides this process actually has a consumer for are applied —
`simulator.customers.baseline_rate_per_minute` and `.basket_size_weights`
feed real code paths (`runner.py`, `session.py`). `courier_offline`'s
`simulator.couriers.spontaneous_offline_probability` is deliberately not
read here: the simulator doesn't simulate couriers at all (dispatch's own
Celery autopilot does, per `dispatch.tasks`), so there is no code path for
that override to change — same reason `config.apply_scenario_overrides`'s
CLI path already refuses `courier_offline` outright rather than silently
applying an override nothing reads.
"""

import asyncio
import contextlib

import httpx

from simulator.client.api import FrontOfHouseClient, FrontOfHouseError

_RATE_KEY = "simulator.customers.baseline_rate_per_minute"
_BASKET_WEIGHTS_KEY = "simulator.customers.basket_size_weights"


class ScenarioOverrideTracker:
    def __init__(self, client: FrontOfHouseClient, *, poll_interval_seconds: float = 5.0) -> None:
        self._client = client
        self._poll_interval_seconds = poll_interval_seconds
        self._overrides: dict[str, object] = {}

    async def run_forever(self) -> None:
        while True:
            # A blip shouldn't crash the run — keep the last known overrides,
            # same as `SpeedTracker`.
            with contextlib.suppress(FrontOfHouseError, httpx.HTTPError):
                self._overrides = await self._client.get_active_scenario_overrides()
            await asyncio.sleep(self._poll_interval_seconds)

    def current_rate_per_minute(self, baseline: float) -> float:
        """Re-read at the point of use (`runner.py`'s `poisson_arrivals`
        callable), never cached into a local — the same "no pre-scaled
        storage" discipline as everything else in this project (SPEC.md §5),
        applied here to a live-tunable parameter instead of a duration."""
        value = self._overrides.get(_RATE_KEY)
        return float(value) if isinstance(value, int | float) else baseline

    def current_basket_size_weights(self, baseline: dict[int, float]) -> dict[int, float]:
        value = self._overrides.get(_BASKET_WEIGHTS_KEY)
        if not isinstance(value, dict):
            return baseline
        return {int(size): float(weight) for size, weight in value.items()}
