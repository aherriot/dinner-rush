import asyncio
import uuid

from simulator.client.api import OrderResult
from simulator.client.models import Address, Customer, MenuItem, Order, OrderStatusEnum
from simulator.config import CustomersConfig, ThinkTimeConfig
from simulator.runner import run


class _FastFakeClient:
    """A client whose every call resolves instantly — real `asyncio` event
    loop, no real network, so the runner's task orchestration (spawn, stop,
    drain) is exercised end to end without a real gateway."""

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
