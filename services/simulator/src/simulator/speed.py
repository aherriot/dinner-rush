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

    async def run_forever(self) -> None:
        while True:
            # keep the last known value on a blip — it shouldn't crash the run
            with contextlib.suppress(GatewayError, httpx.HTTPError):
                self._current = await self._client.get_speed()
            await asyncio.sleep(self._poll_interval_seconds)
