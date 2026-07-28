"""Running counters and a periodic terminal summary — the operator's proof
that `make rush` is doing something concurrent and real, without needing the
board (Phase 8) to watch it happen.
"""

import asyncio
from dataclasses import dataclass


@dataclass
class Stats:
    placed: int = 0
    rejected: int = 0
    abandoned: int = 0
    errors: int = 0
    in_flight: int = 0

    def snapshot(self) -> str:
        return (
            f"in_flight={self.in_flight} placed={self.placed} rejected={self.rejected} "
            f"abandoned={self.abandoned} errors={self.errors}"
        )


async def print_periodically(stats: Stats, *, interval_seconds: float = 5.0) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        print(f"[simulator] {stats.snapshot()}", flush=True)
