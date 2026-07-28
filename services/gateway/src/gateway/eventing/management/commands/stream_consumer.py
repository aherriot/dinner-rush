"""`manage.py stream_consumer --group cg:analytics|cg:ws-fanout` (DECISIONS.md §0003).

`XAUTOCLAIM` runs before every read so messages abandoned by a crashed
consumer (idle past `claim_min_idle_seconds`) get reclaimed and finished by
whichever consumer is alive — the whole mechanism behind the
`docker compose stop dispatch` recovery demo.
"""

import socket
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from dinner_rush_core.config import load_config
from dinner_rush_core.streams import ack, autoclaim, ensure_group, read_batch
from gateway.eventing.handlers import HANDLERS
from gateway.eventing.redis_client import get_redis_client

STREAM = "events:order"  # the only stream gateway produces on until Phase 4/7


class Command(BaseCommand):
    help = "Run one consumer group's XREADGROUP loop against events:order."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--group", required=True, choices=sorted(HANDLERS))
        parser.add_argument("--consumer-name", default=None)

    def handle(self, *_args: Any, group: str, consumer_name: str | None, **_options: Any) -> None:
        handler = HANDLERS[group]
        consumer = consumer_name or f"{socket.gethostname()}-{group}"
        client = get_redis_client()
        config = load_config()

        ensure_group(client, STREAM, group)
        self.stdout.write(self.style.SUCCESS(f"stream_consumer[{group}]: consuming as {consumer}"))

        while True:
            reclaimed = autoclaim(
                client,
                STREAM,
                group,
                consumer,
                min_idle_ms=config.streams.claim_min_idle_seconds * 1000,
                count=config.streams.read_count,
            )
            fresh = read_batch(
                client,
                STREAM,
                group,
                consumer,
                count=config.streams.read_count,
                block_ms=config.streams.read_block_ms,
            )
            for message in [*reclaimed, *fresh]:
                try:
                    handler(message)
                except Exception as exc:
                    self.stderr.write(f"stream_consumer[{group}]: error, will retry — {exc}")
                    continue
                ack(client, STREAM, group, [message.message_id])
