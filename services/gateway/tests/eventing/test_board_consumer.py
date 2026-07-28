import uuid

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from dinner_rush_core.streams import publish
from gateway.asgi import application
from gateway.eventing.redis_client import get_redis_client
from gateway.eventing.writer import build_envelope
from tests.orders.conftest import customer_token, kitchen_token, manager_token


@pytest.mark.django_db(transaction=True)
def test_manager_can_connect_and_gets_live_pushes() -> None:
    token = manager_token()

    async def scenario() -> None:
        communicator = WebsocketCommunicator(application, f"/ws/board/?token={token}")
        connected, _ = await communicator.connect()
        assert connected

        await get_channel_layer().group_send(
            "board",
            {
                "type": "board.event",
                "envelope": {"event_type": "order.ready", "code": "9200"},
                "stream_id": "1700000000000-0",
                "stream": "events:order",
            },
        )
        push = await communicator.receive_json_from()
        assert push == {
            "event_type": "order.ready",
            "code": "9200",
            "stream_id": "1700000000000-0",
            "stream": "events:order",
        }

        await communicator.disconnect()

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_kitchen_role_can_connect() -> None:
    token = kitchen_token()

    async def scenario() -> None:
        communicator = WebsocketCommunicator(application, f"/ws/board/?token={token}")
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_customer_role_is_rejected() -> None:
    token = customer_token(uuid.uuid4())

    async def scenario() -> None:
        communicator = WebsocketCommunicator(application, f"/ws/board/?token={token}")
        connected, _ = await communicator.connect()
        assert not connected

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_missing_token_is_rejected() -> None:
    async def scenario() -> None:
        communicator = WebsocketCommunicator(application, "/ws/board/")
        connected, _ = await communicator.connect()
        assert not connected

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_reconnecting_replays_each_stream_independently() -> None:
    """A board client tracks three positions at once — one per stream — so
    each `?last_event_id_<stream>=` must replay only its own stream, not
    bleed into the others."""
    token = manager_token()
    client = get_redis_client()

    order_event = build_envelope(
        event_type="order.baked",
        aggregate_type="order",
        aggregate_id=uuid.uuid4(),
        sequence=1,
        correlation_id=uuid.uuid4(),
        payload={"code": "9201", "actual_bake_s": 42.0},
    )
    oven_event = build_envelope(
        event_type="oven.down",
        aggregate_type="oven",
        aggregate_id=uuid.uuid4(),
        sequence=1,
        correlation_id=uuid.uuid4(),
        payload={"oven_id": str(uuid.uuid4()), "slot_count": 4},
    )
    order_baseline_id = publish(get_redis_client(), "events:order", order_event)
    oven_baseline_id = publish(get_redis_client(), "events:oven", oven_event)

    missed_order = build_envelope(
        event_type="order.baked",
        aggregate_type="order",
        aggregate_id=uuid.uuid4(),
        sequence=2,
        correlation_id=uuid.uuid4(),
        payload={"code": "9202", "actual_bake_s": 10.0},
    )
    missed_order_id = publish(client, "events:order", missed_order)

    async def scenario() -> None:
        communicator = WebsocketCommunicator(
            application,
            f"/ws/board/?token={token}"
            f"&last_event_id_order={order_baseline_id}"
            f"&last_event_id_oven={oven_baseline_id}",
        )
        connected, _ = await communicator.connect()
        assert connected

        replayed = await communicator.receive_json_from()
        assert replayed["event_id"] == str(missed_order.event_id)
        assert replayed["stream_id"] == missed_order_id
        assert replayed["stream"] == "events:order"

        # Nothing queued on the oven stream past its baseline — no second
        # replay message should arrive.
        assert await communicator.receive_nothing(timeout=0.2)

        await communicator.disconnect()

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_malformed_last_event_id_on_one_stream_does_not_crash_the_connection() -> None:
    token = manager_token()

    async def scenario() -> None:
        bogus = str(uuid.uuid4())
        communicator = WebsocketCommunicator(
            application, f"/ws/board/?token={token}&last_event_id_courier={bogus}"
        )
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async_to_sync(scenario)()
