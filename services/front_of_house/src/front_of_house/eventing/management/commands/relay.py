"""`manage.py relay` — the outbox relay process (DECISIONS.md §0004).

Wakes instantly on `LISTEN outbox_channel`, falls back to a poll every
`streams.outbox_poll_ms` in case a notification is ever missed — which is
also what makes a Redis restart self-healing: the relay just re-publishes
whatever is still unpublished.
"""

from typing import Any

import psycopg
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from dinner_rush_core.config import load_config
from dinner_rush_core.outbox import relay_batch
from dinner_rush_core.streams import publish as stream_publish
from front_of_house.eventing.redis_client import get_redis_client
from front_of_house.eventing.writer import OUTBOX_NOTIFY_CHANNEL


class Command(BaseCommand):
    help = "Relay unpublished outbox rows to Redis Streams."

    def handle(self, *_args: Any, **_options: Any) -> None:
        config = load_config()
        redis_client = get_redis_client()
        poll_seconds = config.streams.outbox_poll_ms / 1000

        listen_conn = psycopg.connect(**connection.get_connection_params(), autocommit=True)
        with listen_conn.cursor() as cursor:
            cursor.execute(f"LISTEN {OUTBOX_NOTIFY_CHANNEL}")

        self.stdout.write(self.style.SUCCESS("relay: listening for outbox rows"))
        while True:
            try:
                self._relay_once(redis_client, config.streams.maxlen)
            except Exception as exc:
                # e.g. the `outbox` table doesn't exist yet because `make up`
                # hasn't run `migrate` — self-correcting once it does.
                self.stderr.write(f"relay: error, will retry — {exc}")
            for _ in listen_conn.notifies(timeout=poll_seconds):
                break  # a NOTIFY arrived early — relay again immediately

    def _relay_once(self, redis_client: Any, maxlen: int) -> None:
        def _publish(row: Any) -> None:
            stream_publish(redis_client, row.stream, row.envelope, maxlen=maxlen)

        with transaction.atomic():
            count = relay_batch(connection.cursor(), _publish, limit=100)
        if count:
            self.stdout.write(f"relay: published {count} event(s)")
