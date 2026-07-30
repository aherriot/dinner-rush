"""Thin, generic HTTP call layer over front-of-house's public API.

Deliberately hand-written and endpoint-generic — everything that could drift
(request/response shapes) comes from the generated `models.py`; this file
just knows how to send JSON and read a status code. Same split as
`apps/web`'s `openapi-typescript` (generated) + `openapi-fetch` (a thin,
generic layer, also hand-written).
"""

import uuid
from dataclasses import dataclass
from types import TracebackType

import httpx

from simulator.client.models import (
    Customer,
    MenuItem,
    Order,
    OrderCreateRequest,
    OrderItemRequest,
    ScenariosActive,
    Speed,
    TokenRequest,
    TokenResponse,
)


class FrontOfHouseError(Exception):
    """A genuine 4xx/5xx — never raised for `rejected`, which is a 202
    success (SPEC.md §3.1), not an error."""

    def __init__(self, status_code: int, detail: object) -> None:
        super().__init__(f"front-of-house returned {status_code}: {detail!r}")
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class OrderResult:
    status_code: int
    order: Order


class FrontOfHouseClient:
    """One shared connection pool for every simulated customer — bearer
    tokens are passed per call, not stored on the client, since hundreds of
    concurrent customer identities share this one instance."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """`transport` is a test seam (`httpx.MockTransport`) — production
        callers never pass it."""
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "FrontOfHouseClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def authenticate_customer(self, email: str) -> str:
        """`POST /auth/token` with just an email (SPEC.md §3.1, ADR 0002 §2)
        — the simulator authenticates exactly like a real customer client."""
        body = TokenRequest(email=email).model_dump(mode="json", exclude_none=True)
        response = await self._http.post("/auth/token", json=body)
        _raise_for_front_of_house_error(response)
        return TokenResponse.model_validate(response.json()).access

    async def get_menu(self) -> list[MenuItem]:
        response = await self._http.get("/menu")
        _raise_for_front_of_house_error(response)
        return [MenuItem.model_validate(item) for item in response.json()]

    async def get_speed(self) -> int:
        response = await self._http.get("/speed")
        _raise_for_front_of_house_error(response)
        return Speed.model_validate(response.json()).speed

    async def get_active_scenario_overrides(self) -> dict[str, object]:
        """`GET /scenarios/active` (SPEC.md §3.2) — public, unauthenticated,
        same reasoning as `get_speed`: this is an ordinary API client with no
        service credentials to read front-of-house's Redis directly (CLAUDE.md §5)."""
        response = await self._http.get("/scenarios/active")
        _raise_for_front_of_house_error(response)
        overrides = ScenariosActive.model_validate(response.json()).overrides
        return overrides if isinstance(overrides, dict) else {}

    async def get_me(self, token: str) -> Customer:
        response = await self._http.get("/me", headers=_bearer(token))
        _raise_for_front_of_house_error(response)
        return Customer.model_validate(response.json())

    async def create_order(
        self, token: str, *, address_id: uuid.UUID, items: list[OrderItemRequest]
    ) -> OrderResult:
        """201 accepted or 202 `status: rejected` are both success (SPEC.md
        §3.1) — only a genuine 4xx/5xx raises."""
        body = OrderCreateRequest(address_id=address_id, items=items).model_dump(mode="json")
        headers = {**_bearer(token), "Idempotency-Key": str(uuid.uuid4())}
        response = await self._http.post("/orders", json=body, headers=headers)
        _raise_for_front_of_house_error(response)
        order = Order.model_validate(response.json())
        return OrderResult(status_code=response.status_code, order=order)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _raise_for_front_of_house_error(response: httpx.Response) -> None:
    if response.status_code >= 400:
        try:
            detail: object = response.json()
        except ValueError:
            detail = response.text
        raise FrontOfHouseError(response.status_code, detail)
