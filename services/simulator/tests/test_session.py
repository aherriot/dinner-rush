import random
import uuid

import pytest

from simulator.client.api import GatewayError, OrderResult
from simulator.client.models import Address, Customer, MenuItem, Order, StatusEnum
from simulator.config import CustomersConfig, ThinkTimeConfig
from simulator.session import Simulation
from simulator.speed import SpeedTracker
from simulator.stats import Stats


class _FakeClient:
    def __init__(self) -> None:
        self.authenticate_calls: list[str] = []
        self.get_me_calls: list[str] = []
        self.create_order_calls: list[str] = []
        self.order_status: StatusEnum = StatusEnum.accepted
        self.auth_error = False
        self.order_error = False

    async def get_menu(self) -> list[MenuItem]:
        return [
            MenuItem(
                id=uuid.uuid4(),
                sku="MARG",
                name="Margherita",
                base_price_cents=1200,
                prep_seconds=90,
                bake_seconds=420,
                available=True,
            ),
            MenuItem(
                id=uuid.uuid4(),
                sku="HIDDEN",
                name="Hidden",
                base_price_cents=100,
                prep_seconds=1,
                bake_seconds=1,
                available=False,
            ),
        ]

    async def authenticate_customer(self, email: str) -> str:
        self.authenticate_calls.append(email)
        if self.auth_error:
            raise GatewayError(401, "nope")
        return f"token-for-{email}"

    async def get_me(self, token: str) -> Customer:
        self.get_me_calls.append(token)
        return Customer(
            id=uuid.uuid4(),
            name="Sim Customer",
            email="sim0001@example.com",
            addresses=[Address(id=uuid.uuid4(), line1="1 Sim St", grid_x=50, grid_y=50)],
        )

    async def create_order(self, token: str, *, address_id: object, items: object) -> OrderResult:
        self.create_order_calls.append(token)
        if self.order_error:
            raise GatewayError(422, "bad request")
        return OrderResult(
            status_code=201 if self.order_status == StatusEnum.accepted else 202,
            order=Order(
                id=uuid.uuid4(),
                code="4400",
                status=self.order_status,
                subtotal_cents=1200,
                delivery_fee_cents=299,
                total_cents=1499,
                placed_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
                items=[],
                late=False,
            ),
        )


def _config(**overrides: object) -> CustomersConfig:
    defaults: dict[str, object] = {
        "arrival": "poisson",
        "baseline_rate_per_minute": 6,
        "think_time_seconds": ThinkTimeConfig(min=0, max=0),
        "basket_size_weights": {1: 1.0},
        "cancel_probability": 0.0,
        "repeat_customer_probability": 0.0,
        "population": 10,
    }
    defaults.update(overrides)
    return CustomersConfig(**defaults)  # type: ignore[arg-type]


async def _no_sleep(_seconds: float) -> None:
    return None


def _simulation(
    client: _FakeClient, config: CustomersConfig, *, seed: int = 1
) -> tuple[Simulation, Stats]:
    speed = SpeedTracker(client, initial=1)  # type: ignore[arg-type]
    stats = Stats()
    sim = Simulation(
        client,  # type: ignore[arg-type]
        config,
        speed,
        stats,
        rng=random.Random(seed),
        sleep=_no_sleep,
    )
    return sim, stats


async def test_a_successful_arrival_places_an_order_and_counts_it() -> None:
    client = _FakeClient()
    sim, stats = _simulation(client, _config())
    await sim.load_menu()

    await sim.run_one_arrival()

    assert stats.placed == 1
    assert stats.errors == 0
    assert len(client.create_order_calls) == 1


async def test_a_rejected_order_is_counted_as_rejected_not_an_error() -> None:
    client = _FakeClient()
    client.order_status = StatusEnum.rejected
    sim, stats = _simulation(client, _config())
    await sim.load_menu()

    await sim.run_one_arrival()

    assert stats.rejected == 1
    assert stats.placed == 0
    assert stats.errors == 0


async def test_cancel_probability_one_abandons_before_ordering() -> None:
    client = _FakeClient()
    sim, stats = _simulation(client, _config(cancel_probability=1.0))
    await sim.load_menu()

    await sim.run_one_arrival()

    assert stats.abandoned == 1
    assert stats.placed == 0
    assert len(client.create_order_calls) == 0


async def test_auth_failure_counts_as_an_error_and_does_not_raise() -> None:
    client = _FakeClient()
    client.auth_error = True
    sim, stats = _simulation(client, _config())
    await sim.load_menu()

    await sim.run_one_arrival()

    assert stats.errors == 1
    assert len(client.create_order_calls) == 0


async def test_order_failure_counts_as_an_error() -> None:
    client = _FakeClient()
    client.order_error = True
    sim, stats = _simulation(client, _config())
    await sim.load_menu()

    await sim.run_one_arrival()

    assert stats.errors == 1


async def test_token_and_address_are_cached_across_repeat_arrivals() -> None:
    client = _FakeClient()
    sim, _stats = _simulation(client, _config(repeat_customer_probability=1.0))
    await sim.load_menu()

    await sim.run_one_arrival()  # first arrival: no recent pool yet, picks fresh
    await sim.run_one_arrival()  # repeat_customer_probability=1.0 now reuses it

    assert len(client.authenticate_calls) == 1
    assert len(client.get_me_calls) == 1
    assert client.authenticate_calls[0] == client.authenticate_calls[-1]


async def test_unavailable_menu_items_are_never_ordered() -> None:
    client = _FakeClient()
    sim, _stats = _simulation(client, _config())
    await sim.load_menu()

    assert all(item.sku != "HIDDEN" for item in sim.menu)


@pytest.mark.parametrize("seed", range(5))
async def test_many_arrivals_never_crash(seed: int) -> None:
    client = _FakeClient()
    sim, stats = _simulation(
        client, _config(cancel_probability=0.3, repeat_customer_probability=0.5), seed=seed
    )
    await sim.load_menu()

    for _ in range(20):
        await sim.run_one_arrival()

    assert stats.errors == 0
