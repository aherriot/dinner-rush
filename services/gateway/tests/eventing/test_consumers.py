import uuid

import pytest
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator

from dinner_rush_core.streams import publish
from gateway.asgi import application
from gateway.customers.models import Address, Customer
from gateway.eventing.consumers import STREAM
from gateway.eventing.redis_client import get_redis_client
from gateway.eventing.writer import build_envelope
from gateway.orders.models import Order
from tests.orders.conftest import customer_token, manager_token


def _order(customer: Customer, address: Address, code: str) -> Order:
    return Order.objects.create(
        code=code,
        customer=customer,
        address=address,
        status="accepted",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
    )


@pytest.mark.django_db(transaction=True)
def test_owning_customer_can_connect_and_gets_live_pushes(
    customer_with_address: tuple[Customer, Address],
) -> None:
    customer, address = customer_with_address
    order = _order(customer, address, "9100")
    token = customer_token(customer.id)

    async def scenario() -> None:
        communicator = WebsocketCommunicator(application, f"/ws/orders/9100/?token={token}")
        connected, _ = await communicator.connect()
        assert connected

        from channels.layers import get_channel_layer

        await get_channel_layer().group_send(
            f"order.{order.id}",
            {
                "type": "order.event",
                "envelope": {"event_type": "order.ready", "code": "9100"},
                "stream_id": "1700000000000-0",
            },
        )
        push = await communicator.receive_json_from()
        assert push == {"event_type": "order.ready", "code": "9100", "stream_id": "1700000000000-0"}

        await communicator.disconnect()

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_other_customer_is_rejected(customer_with_address: tuple[Customer, Address]) -> None:
    customer, address = customer_with_address
    _order(customer, address, "9101")

    other = Customer.objects.create(name="Grace Hopper", email="grace@example.com")
    token = customer_token(other.id)

    async def scenario() -> None:
        communicator = WebsocketCommunicator(application, f"/ws/orders/9101/?token={token}")
        connected, _ = await communicator.connect()
        assert not connected

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_manager_can_connect_to_any_order(customer_with_address: tuple[Customer, Address]) -> None:
    customer, address = customer_with_address
    _order(customer, address, "9102")
    token = manager_token()

    async def scenario() -> None:
        communicator = WebsocketCommunicator(application, f"/ws/orders/9102/?token={token}")
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_missing_token_is_rejected(customer_with_address: tuple[Customer, Address]) -> None:
    customer, address = customer_with_address
    _order(customer, address, "9103")

    async def scenario() -> None:
        communicator = WebsocketCommunicator(application, "/ws/orders/9103/")
        connected, _ = await communicator.connect()
        assert not connected

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_reconnecting_with_last_event_id_replays_the_gap(
    customer_with_address: tuple[Customer, Address],
) -> None:
    """The mid-order refresh case (PHASES.md Phase 3 'done means')."""
    customer, address = customer_with_address
    order = _order(customer, address, "9104")
    token = customer_token(customer.id)

    client = get_redis_client()
    stream_key = STREAM
    missed = build_envelope(
        event_type="order.baked",
        aggregate_type="order",
        aggregate_id=order.id,
        sequence=5,
        correlation_id=order.id,
        payload={"code": "9104", "actual_bake_s": 42.0},
    )
    unrelated_order_event = build_envelope(
        event_type="order.baked",
        aggregate_type="order",
        aggregate_id=uuid.uuid4(),
        sequence=1,
        correlation_id=uuid.uuid4(),
        payload={"code": "0000", "actual_bake_s": 1.0},
    )
    last_seen_id = publish(client, stream_key, unrelated_order_event)
    missed_stream_id = publish(client, stream_key, missed)

    async def scenario() -> None:
        communicator = WebsocketCommunicator(
            application, f"/ws/orders/9104/?token={token}&last_event_id={last_seen_id}"
        )
        connected, _ = await communicator.connect()
        assert connected

        replayed = await communicator.receive_json_from()
        assert replayed["event_id"] == str(missed.event_id)
        # Regression: this must be the real Redis stream id, not
        # `missed.event_id` — that's what a client is expected to send back
        # as the next `?last_event_id=`, and only a genuine stream id
        # survives `XRANGE` there.
        assert replayed["stream_id"] == missed_stream_id

        await communicator.disconnect()

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_reconnecting_with_a_malformed_last_event_id_does_not_crash_the_connection(
    customer_with_address: tuple[Customer, Address],
) -> None:
    """Regression: `?last_event_id=` used to receive the envelope's own
    `event_id` (a business UUID) instead of the real Redis stream id
    (`test_reconnecting_with_last_event_id_replays_the_gap`, above, covers
    the fix at the source). A client sending a malformed value here — an old
    cached frontend, a bug, a bad actor — used to crash the whole connection
    (`XRANGE` raising `ResponseError`, uncaught, closing with code 1011)
    instead of just skipping the replay."""
    customer, address = customer_with_address
    _order(customer, address, "9105")
    token = customer_token(customer.id)

    async def scenario() -> None:
        bogus_last_event_id = str(uuid.uuid4())
        communicator = WebsocketCommunicator(
            application, f"/ws/orders/9105/?token={token}&last_event_id={bogus_last_event_id}"
        )
        connected, _ = await communicator.connect()
        assert connected  # must not crash — a malformed last_event_id just skips replay

        await communicator.disconnect()

    async_to_sync(scenario)()
