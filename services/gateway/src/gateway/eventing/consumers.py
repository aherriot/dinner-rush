"""`WS /ws/orders/{code}` (SPEC.md §3.1) — replay + live fanout.

Browsers can't set an `Authorization` header on a native `WebSocket`, so the
access token travels as `?token=`. `?last_event_id=` triggers a replay via
`XRANGE` before the socket switches to live pushes fed by `cg:ws-fanout`
(`handlers.handle_ws_fanout`) — refreshing mid-order misses nothing
(DECISIONS.md §0003).
"""

from typing import Any
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from dinner_rush_core.streams import read_range
from gateway.eventing.redis_client import get_redis_client
from gateway.orders.models import Order

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
        await self.send_json(message["envelope"])

    @sync_to_async
    def _get_order(self, code: str) -> dict[str, str] | None:
        order = Order.objects.filter(code=code).first()
        if order is None:
            return None
        return {"id": str(order.id), "customer_id": str(order.customer_id)}

    async def _replay(self, order_id: str, last_event_id: str) -> None:
        client = get_redis_client()
        messages = await sync_to_async(read_range)(client, STREAM, last_event_id)
        for message in messages:
            if str(message.envelope.aggregate_id) == order_id:
                await self.send_json(message.envelope.model_dump(mode="json"))


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
