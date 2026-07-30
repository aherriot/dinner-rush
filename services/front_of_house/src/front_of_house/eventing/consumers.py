"""`WS /ws/orders/{code}` (SPEC.md §3.1) — replay + live fanout.

Browsers can't set an `Authorization` header on a native `WebSocket`, so the
access token travels as `?token=`. `?last_event_id=` triggers a replay via
`XRANGE` before the socket switches to live pushes fed by `cg:ws-fanout`
(`handlers.handle_ws_fanout`) — refreshing mid-order misses nothing
(DECISIONS.md §0003).

`?last_event_id=` must be a genuine Redis stream id (`<ms>-<seq>`), not the
envelope's own `event_id` (a business UUID, used for idempotency elsewhere,
unrelated to stream position) — every message this consumer sends carries
both under different names (`stream_id` vs the envelope's own `event_id`)
specifically so the browser never conflates them when it echoes one back.
"""

from typing import Any
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from redis.exceptions import ResponseError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from dinner_rush_core.streams import read_range
from front_of_house.eventing.redis_client import get_redis_client
from front_of_house.orders.models import Order

STREAM = "events:order"
VALID_ROLES = {"customer", "manager", "kitchen"}


class OrderTrackerConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        code = self.scope["url_route"]["kwargs"]["code"]
        query = parse_qs(self.scope["query_string"].decode())
        token = query.get("token", [None])[0]
        last_event_id = query.get("last_event_id", [None])[0]

        actor = _authenticate(token)
        if actor is None:
            await self.close(code=4401)
            return

        order = await self._get_order(code)
        if order is None:
            await self.close(code=4404)
            return

        if not _authorized(actor, order):
            await self.close(code=4403)
            return

        self.group_name = f"order.{order['id']}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        if last_event_id:
            await self._replay(order["id"], last_event_id)

    async def disconnect(self, _code: int) -> None:
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def order_event(self, message: dict[str, Any]) -> None:
        """Dispatched for `{"type": "order.event", ...}` group_sends."""
        await self.send_json({**message["envelope"], "stream_id": message["stream_id"]})

    @sync_to_async
    def _get_order(self, code: str) -> dict[str, str] | None:
        order = Order.objects.filter(code=code).first()
        if order is None:
            return None
        return {"id": str(order.id), "customer_id": str(order.customer_id)}

    async def _replay(self, order_id: str, last_event_id: str) -> None:
        client = get_redis_client()
        try:
            messages = await sync_to_async(read_range)(client, STREAM, last_event_id)
        except ResponseError:
            # `last_event_id` is client-controlled input over a WS query
            # param — a malformed or stale value (e.g. sent before this
            # fix shipped) shouldn't take the connection down; just skip
            # the replay and let live fanout carry on from here.
            return
        for message in messages:
            if str(message.envelope.aggregate_id) == order_id:
                await self.send_json(
                    {**message.envelope.model_dump(mode="json"), "stream_id": message.message_id}
                )


#: Query param -> the physical stream it replays (SPEC.md §4's fixed three).
#: A board client tracks a position per stream, unlike `OrderTrackerConsumer`
#: which only ever replays one.
BOARD_STREAMS_BY_QUERY_PARAM = {
    "last_event_id_order": "events:order",
    "last_event_id_oven": "events:oven",
    "last_event_id_courier": "events:courier",
}
BOARD_VALID_ROLES = {"kitchen", "manager"}


class BoardConsumer(AsyncJsonWebsocketConsumer):
    """`WS /ws/board` (SPEC.md §3.1) — kitchen/manager only. Unlike
    `OrderTrackerConsumer` there is no single order to own, so there's no
    per-object authorization check, only the role gate. Fed by three
    `stream_consumer` processes sharing the `cg:ws-board-fanout` group name,
    one per stream (`handlers.handle_board_fanout`, compose.yaml) — a Redis
    consumer group is scoped to a single stream, the same reason
    `cg:order-sync` already runs as two processes for `events:order` and
    `events:courier`.
    """

    async def connect(self) -> None:
        query = parse_qs(self.scope["query_string"].decode())
        token = query.get("token", [None])[0]

        actor = _authenticate(token)
        if actor is None:
            await self.close(code=4401)
            return
        if actor["role"] not in BOARD_VALID_ROLES:
            await self.close(code=4403)
            return

        self.group_name = "board"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        for param, stream in BOARD_STREAMS_BY_QUERY_PARAM.items():
            last_event_id = query.get(param, [None])[0]
            if last_event_id:
                await self._replay(stream, last_event_id)

    async def disconnect(self, _code: int) -> None:
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def board_event(self, message: dict[str, Any]) -> None:
        """Dispatched for `{"type": "board.event", ...}` group_sends."""
        await self.send_json(
            {
                **message["envelope"],
                "stream_id": message["stream_id"],
                "stream": message["stream"],
            }
        )

    async def _replay(self, stream: str, last_event_id: str) -> None:
        client = get_redis_client()
        try:
            messages = await sync_to_async(read_range)(client, stream, last_event_id)
        except ResponseError:
            # Same reasoning as `OrderTrackerConsumer._replay`: client-
            # controlled input, so a malformed/stale id skips the replay
            # rather than taking the connection down.
            return
        for message in messages:
            await self.send_json(
                {
                    **message.envelope.model_dump(mode="json"),
                    "stream_id": message.message_id,
                    "stream": stream,
                }
            )


def _authenticate(token: str | None) -> dict[str, str | None] | None:
    if not token:
        return None
    try:
        # simplejwt's own hint is `Token | None`; documented/actual usage is
        # a raw token string (same mismatch noted in authentication.py).
        access = AccessToken(token)  # type: ignore[arg-type]
    except TokenError:
        return None
    role = access.get("role")
    if role not in VALID_ROLES:
        return None
    return {"role": role, "customer_id": access.get("customer_id")}


def _authorized(actor: dict[str, str | None], order: dict[str, str]) -> bool:
    if actor["role"] == "manager":
        return True
    return actor["role"] == "customer" and actor["customer_id"] == order["customer_id"]
