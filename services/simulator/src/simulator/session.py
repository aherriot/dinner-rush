"""One simulated customer's ordering session, run once per Poisson arrival.

Cancellation is deliberately not an API call — SPEC.md has no cancel
endpoint, and the project's own rule ("if you find yourself wanting to
bypass the API to make the simulator work, the API is wrong — fix the API")
cuts the other way here too: nothing in the API needs inventing for a
customer who changes their mind before ever placing the order.
`cancel_probability` is cart abandonment, not a `DELETE /orders/{id}` this
project doesn't have.
"""

import asyncio
import random
import uuid
from collections import deque
from collections.abc import Awaitable, Callable

from simulator.client.api import GatewayClient, GatewayError
from simulator.client.models import MenuItem, OrderItemRequest
from simulator.config import CustomersConfig
from simulator.population import customer_email
from simulator.scenario_overrides import ScenarioOverrideTracker
from simulator.speed import SpeedTracker
from simulator.stats import Stats

_RECENT_POOL_MAXLEN = 30


class Simulation:
    """Shared, mutable state one Poisson arrival loop draws on: token and
    address caches (ordinary session reuse, same as any real client would
    do), the menu snapshot, and a bounded pool of recently-active customers
    for `repeat_customer_probability`.
    """

    def __init__(
        self,
        client: GatewayClient,
        config: CustomersConfig,
        speed: SpeedTracker,
        stats: Stats,
        *,
        scenario_overrides: ScenarioOverrideTracker | None = None,
        rng: random.Random | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._config = config
        self._speed = speed
        self._stats = stats
        self._scenario_overrides = scenario_overrides
        self._rng = rng or random.Random()
        self._sleep = sleep

        self._menu: list[MenuItem] = []
        self._tokens: dict[str, str] = {}
        self._addresses: dict[str, uuid.UUID] = {}
        self._recent: deque[str] = deque(maxlen=_RECENT_POOL_MAXLEN)

    @property
    def menu(self) -> list[MenuItem]:
        return list(self._menu)

    async def load_menu(self) -> None:
        self._menu = [item for item in await self._client.get_menu() if item.available is not False]

    async def run_one_arrival(self) -> None:
        self._stats.in_flight += 1
        try:
            await self._run_one_arrival()
        finally:
            self._stats.in_flight -= 1

    async def _run_one_arrival(self) -> None:
        email = self._pick_customer()

        try:
            token = await self._authenticated(email)
            address_id = await self._address_for(email, token)
        except GatewayError:
            self._stats.errors += 1
            return

        think_time = self._rng.uniform(
            self._config.think_time_seconds.min, self._config.think_time_seconds.max
        )
        await self._sleep_domain_seconds(think_time)

        self._recent.append(email)

        if self._rng.random() < self._config.cancel_probability:
            self._stats.abandoned += 1
            return

        items = self._pick_basket()
        if not items:
            return  # nothing available to order right now (shortage scenario territory)

        try:
            result = await self._client.create_order(token, address_id=address_id, items=items)
        except GatewayError:
            self._stats.errors += 1
            return

        if result.order.status is not None and result.order.status.value == "rejected":
            self._stats.rejected += 1
        else:
            self._stats.placed += 1

    def _pick_customer(self) -> str:
        if self._recent and self._rng.random() < self._config.repeat_customer_probability:
            return self._rng.choice(self._recent)
        n = self._rng.randint(1, self._config.population)
        return customer_email(n)

    async def _authenticated(self, email: str) -> str:
        cached = self._tokens.get(email)
        if cached is not None:
            return cached
        token = await self._client.authenticate_customer(email)
        self._tokens[email] = token
        return token

    async def _address_for(self, email: str, token: str) -> uuid.UUID:
        cached = self._addresses.get(email)
        if cached is not None:
            return cached
        customer = await self._client.get_me(token)
        address_id = customer.addresses[0].id
        self._addresses[email] = address_id
        return address_id

    def _pick_basket(self) -> list[OrderItemRequest]:
        if not self._menu:
            return []
        weights = self._config.basket_size_weights
        if self._scenario_overrides is not None:
            weights = self._scenario_overrides.current_basket_size_weights(weights)
        [size] = self._rng.choices(list(weights.keys()), weights=list(weights.values()), k=1)
        chosen = self._rng.choices(self._menu, k=size)
        return [OrderItemRequest(sku=item.sku, qty=1) for item in chosen]

    async def _sleep_domain_seconds(self, domain_seconds: float) -> None:
        await self._sleep(domain_seconds / self._speed.current)
