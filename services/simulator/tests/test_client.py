import uuid

import httpx
import pytest

from simulator.client.api import FrontOfHouseClient, FrontOfHouseError
from simulator.client.models import OrderItemRequest


def _client(handler: httpx.MockTransport) -> FrontOfHouseClient:
    return FrontOfHouseClient("http://front-of-house", transport=handler)


async def test_authenticate_customer_posts_just_the_email_and_returns_the_access_token() -> None:
    captured: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, json={"access": "tok-abc", "refresh": "tok-refresh"})

    client = _client(httpx.MockTransport(handler))
    token = await client.authenticate_customer("ada@example.com")

    assert token == "tok-abc"
    assert b"ada@example.com" in captured["body"]
    assert b"username" not in captured["body"]


async def test_create_order_sends_a_fresh_idempotency_key_and_the_bearer_token() -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            201,
            json={
                "id": str(uuid.uuid4()),
                "code": "4400",
                "status": "accepted",
                "subtotal_cents": 1200,
                "delivery_fee_cents": 299,
                "total_cents": 1499,
                "placed_at": "2026-01-01T00:00:00Z",
                "items": [],
                "late": False,
            },
        )

    client = _client(httpx.MockTransport(handler))
    result = await client.create_order(
        "tok-abc", address_id=uuid.uuid4(), items=[OrderItemRequest(sku="MARG", qty=1)]
    )

    assert result.status_code == 201
    assert result.order.status.value == "accepted"
    request = captured["request"]
    assert request.headers["authorization"] == "Bearer tok-abc"
    assert request.headers["idempotency-key"]


async def test_a_4xx_response_raises_front_of_house_error_not_a_silent_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "unknown sku"})

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(FrontOfHouseError) as exc_info:
        await client.create_order(
            "tok-abc", address_id=uuid.uuid4(), items=[OrderItemRequest(sku="NOPE", qty=1)]
        )
    assert exc_info.value.status_code == 422


async def test_a_202_rejected_order_is_a_success_not_an_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            202,
            json={
                "id": str(uuid.uuid4()),
                "code": "4401",
                "status": "rejected",
                "rejection_reason": "at_capacity",
                "subtotal_cents": 1200,
                "delivery_fee_cents": 299,
                "total_cents": 1499,
                "placed_at": "2026-01-01T00:00:00Z",
                "items": [],
                "late": False,
            },
        )

    client = _client(httpx.MockTransport(handler))
    result = await client.create_order(
        "tok-abc", address_id=uuid.uuid4(), items=[OrderItemRequest(sku="MARG", qty=1)]
    )

    assert result.status_code == 202
    assert result.order.status.value == "rejected"


async def test_get_menu_parses_a_list_of_menu_items() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(uuid.uuid4()),
                    "sku": "MARG",
                    "name": "Margherita",
                    "base_price_cents": 1200,
                    "prep_seconds": 90,
                    "bake_seconds": 420,
                    "available": True,
                }
            ],
        )

    client = _client(httpx.MockTransport(handler))
    menu = await client.get_menu()

    assert len(menu) == 1
    assert menu[0].sku == "MARG"
    assert menu[0].available is True
