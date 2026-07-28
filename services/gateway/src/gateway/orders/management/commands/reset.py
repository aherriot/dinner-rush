"""`make reset` — fast in-place reset for a fresh demo, gateway's half.

Clears orders and the event spine (so the board starts empty and the
order-code sequence restarts at #1) and drops the volatile Redis state a
prior demo run could have left behind: the `events:*` stream backlogs,
any still-live chaos scenario override, and a non-default SPEED. It does
*not* touch the menu, customers or staff logins `make seed` created —
those aren't demo state, they're fixtures, and re-seeding them is a
separate, explicit step (`make seed`) if they're gone too.

Kitchen and dispatch have their own halves of this reset
(`kitchen.cli reset`, `dispatch.cli reset`) since each owns its own
database; `make reset` runs all three.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import connection

from gateway.board.scenario_state import OVERRIDE_SCENARIOS, clear_override
from gateway.eventing.models import EventTypeCounter, Outbox, ProcessedEvent
from gateway.eventing.redis_client import get_redis_client
from gateway.orders.models import Order, OrderCodeSequence, OrderItem, OrderStatusEvent

STREAMS_TO_TRIM = ("events:order", "events:oven", "events:courier")
SPEED_KEY = "dinner_rush:speed"


class Command(BaseCommand):
    help = "Fast in-place reset for a fresh demo: clears orders and the event spine."

    def handle(self, *args: Any, **options: Any) -> None:
        tables = [
            Order._meta.db_table,
            OrderItem._meta.db_table,
            OrderStatusEvent._meta.db_table,
            OrderCodeSequence._meta.db_table,
            Outbox._meta.db_table,
            ProcessedEvent._meta.db_table,
            EventTypeCounter._meta.db_table,
        ]
        with connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE")

        client = get_redis_client()
        for stream in STREAMS_TO_TRIM:
            client.xtrim(stream, maxlen=0)
        for name in OVERRIDE_SCENARIOS:
            clear_override(name)
        client.delete(SPEED_KEY)

        self.stdout.write(
            self.style.SUCCESS(
                "reset: orders and event spine cleared, order codes restart at #1, "
                "stream backlogs and chaos overrides dropped"
            )
        )
