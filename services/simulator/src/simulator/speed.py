"""Tracks gateway's live `SPEED` so every domain-time sleep in this process
divides by it at the point of use (SPEC.md §5) — the same standing rule that
applies to every service applies to this ordinary API client too, and it has
no privileged scope to read Redis directly the way a service would.
"""

import asyncio
import contextlib

import httpx

from simulator.client.api import GatewayClient, GatewayError


class SpeedTracker:
    def __init__(
        self, client: GatewayClient, *, poll_interval_seconds: float = 10.0, initial: int = 1
    ) -> None:
        self._client = client
        self._poll_interval_seconds = poll_interval_seconds
        self._current = initial

    @property
    def current(self) -> int:
        return self._current

    async def refresh(self) -> None:
        """One fetch, on demand rather than on `run_forever`'s own timer —
        `runner.run` awaits this once, before the arrivals loop starts, so
        the very first Poisson interarrival draw already sees the real
        speed instead of `initial`. Without it, an admin who sets SPEED=10
        *before* starting `make sim` still gets a first arrival drawn at
        speed=1 (mean 60s at the 1/min baseline) purely because
        `run_forever`'s background poll hasn't completed by the time the
        arrivals loop takes its first synchronous read of `.current` —
        every arrival after that first one is fine, only the first is
        wrong, which reads as "10x isn't doing anything" for up to a
        couple of minutes by chance."""
        # keep the last known value on a blip — it shouldn't crash the run
        with contextlib.suppress(GatewayError, httpx.HTTPError):
            self._current = await self._client.get_speed()

    async def run_forever(self) -> None:
        while True:
            await self.refresh()
            await asyncio.sleep(self._poll_interval_seconds)
