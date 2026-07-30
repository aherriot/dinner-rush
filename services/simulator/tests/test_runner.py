import asyncio
import random
import uuid

from simulator.client.api import OrderResult
from simulator.client.models import Address, Customer, MenuItem, Order, OrderStatusEnum
from simulator.config import CustomersConfig, ThinkTimeConfig
from simulator.runner import run


class _FastFakeClient:
    """A client whose every call resolves instantly — real `asyncio` event
    loop, no real network, so the runner's task orchestration (spawn, stop,
    drain) is exercised end to end without a real front-of-house."""

    async def get_speed(self) -> int:
        return 1

    async def get_active_scenario_overrides(self) -> dict[str, object]:
        return {}

    async def get_menu(self) -> list[MenuItem]:
        return [
            MenuItem(
                id=uuid.uuid4(),
                sku="MARG",
                name="Margherita",
                base_price_cents=1200,
                prep_seconds=1,
                bake_seconds=1,
                available=True,
            )
        ]

    async def authenticate_customer(self, email: str) -> str:
        return f"token-{email}"

    async def get_me(self, token: str) -> Customer:
        return Customer(
            id=uuid.uuid4(),
            name="Sim",
            email="sim0001@example.com",
            addresses=[Address(id=uuid.uuid4(), line1="1 St", grid_x=50, grid_y=50)],
        )

    async def create_order(self, token: str, *, address_id: object, items: object) -> OrderResult:
        return OrderResult(
            status_code=201,
            order=Order(
                id=uuid.uuid4(),
                code="4400",
                status=OrderStatusEnum.accepted,
                subtotal_cents=1200,
                delivery_fee_cents=299,
                total_cents=1499,
                placed_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
                items=[],
                late=False,
            ),
        )


def _config() -> CustomersConfig:
    return CustomersConfig(
        arrival="poisson",
        baseline_rate_per_minute=6000,  # fast — many arrivals in a fraction of a second
        think_time_seconds=ThinkTimeConfig(min=0, max=0),
        basket_size_weights={1: 1.0},
        cancel_probability=0.0,
        repeat_customer_probability=0.5,
        population=50,
    )


async def test_run_stops_at_duration_and_reports_placed_orders() -> None:
    stats = await run(_FastFakeClient(), _config(), duration_seconds=0.2)  # type: ignore[arg-type]

    assert stats.placed > 0
    assert stats.in_flight == 0


async def test_run_stops_promptly_when_the_stop_event_is_set() -> None:
    stop_event = asyncio.Event()
    stop_event.set()

    stats = await run(_FastFakeClient(), _config(), stop_event=stop_event)  # type: ignore[arg-type]

    assert stats.in_flight == 0


class _HighSpeedClient(_FastFakeClient):
    """Reports a real, already-set SPEED far above the default — the exact
    situation an admin setting SPEED=10 on the board *before* running
    `make sim` puts the simulator in. The `asyncio.sleep(0)` is not
    decorative: a fake `get_speed` that returns without ever actually
    suspending resolves within `speed_task`'s own first turn on the event
    loop regardless of scheduling order, which would make this test pass
    even against the old, unfixed `runner.py` — it doesn't reproduce the
    real race, which depends on the arrivals loop's first (synchronous)
    read of `speed.current` having a genuine chance to run *before* a
    network round trip completes. A real `get_speed()` call always
    suspends at least once; this fake needs to as well."""

    async def get_speed(self) -> int:
        await asyncio.sleep(0)
        return 1000


async def test_the_first_arrival_already_uses_the_speed_set_before_the_run_started() -> None:
    """Regression test: `SpeedTracker` used to start at its `initial=1`
    default and only learn the real speed via a background poll
    (`speed.run_forever`) — a poll that hadn't necessarily completed by the
    time the arrivals loop took its first synchronous read of
    `speed.current`. That made the very first Poisson interarrival always
    drawn at speed=1 regardless of what SPEED front-of-house actually reported,
    which reads as "the fast setting isn't doing anything" for however
    long that one draw takes (mean 60s at this test's baseline rate).

    `random.seed` makes the draw deterministic rather than probabilistic:
    at the real speed (1000x), the mean interarrival is 1/1000th of the
    baseline (60ms vs 60s) — reachable inside this test's 0.5s duration
    only because `runner.run` now fetches the real speed before the
    arrivals loop's first draw, not after it.
    """
    random.seed(20260730)
    config = CustomersConfig(
        arrival="poisson",
        baseline_rate_per_minute=1,
        think_time_seconds=ThinkTimeConfig(min=0, max=0),
        basket_size_weights={1: 1.0},
        cancel_probability=0.0,
        repeat_customer_probability=0.5,
        population=50,
    )

    stats = await run(_HighSpeedClient(), config, duration_seconds=0.5)  # type: ignore[arg-type]

    assert stats.placed > 0
