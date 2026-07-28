"""Wires Poisson arrivals, customer sessions, the speed tracker and the
stats printer into one running simulation — the piece `cli.py` drives for
both the indefinite baseline run (`make sim`) and a time-boxed scenario run
(`make rush`).
"""

import asyncio
import contextlib

from simulator.arrivals import poisson_arrivals
from simulator.client.api import GatewayClient
from simulator.config import CustomersConfig
from simulator.session import Simulation
from simulator.speed import SpeedTracker
from simulator.stats import Stats, print_periodically


async def run(
    client: GatewayClient,
    config: CustomersConfig,
    *,
    duration_seconds: float | None = None,
    stop_event: asyncio.Event | None = None,
) -> Stats:
    """Runs until `stop_event` is set (SIGTERM/SIGINT, `cli.py`), for
    `duration_seconds` (a scenario), or forever (the baseline) — whichever
    comes first. Always returns normally with the final `Stats`, never by
    letting a cancellation propagate out: new arrivals stop being spawned,
    but sessions already in flight are allowed to finish rather than being
    yanked mid-order.
    """
    stats = Stats()
    speed = SpeedTracker(client)
    simulation = Simulation(client, config, speed, stats)
    await simulation.load_menu()

    session_tasks: set[asyncio.Task[None]] = set()

    def _spawn_session() -> None:
        task = asyncio.create_task(simulation.run_one_arrival())
        session_tasks.add(task)
        task.add_done_callback(session_tasks.discard)

    async def _drive_arrivals() -> None:
        arrivals = poisson_arrivals(
            lambda: config.baseline_rate_per_minute, speed=lambda: speed.current
        )
        async for _ in arrivals:
            _spawn_session()

    speed_task = asyncio.create_task(speed.run_forever())
    stats_task = asyncio.create_task(print_periodically(stats))
    arrivals_task = asyncio.create_task(_drive_arrivals())

    stop_waiters: list[asyncio.Task[object]] = [arrivals_task]
    if stop_event is not None:
        stop_waiters.append(asyncio.create_task(stop_event.wait()))
    if duration_seconds is not None:
        stop_waiters.append(asyncio.create_task(asyncio.sleep(duration_seconds)))

    await asyncio.wait(stop_waiters, return_when=asyncio.FIRST_COMPLETED)

    all_tasks = [arrivals_task, speed_task, stats_task, *stop_waiters]
    for task in all_tasks:
        task.cancel()
    if session_tasks:
        await asyncio.gather(*session_tasks, return_exceptions=True)
    for task in all_tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task

    return stats
