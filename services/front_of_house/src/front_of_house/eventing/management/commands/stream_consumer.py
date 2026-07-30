"""`manage.py stream_consumer --group cg:analytics|cg:ws-fanout|cg:order-sync
[--stream events:order|events:courier]` (DECISIONS.md §0003).

`--stream` defaults to `events:order`, the only one front-of-house needed through
Phase 4. Phase 7 adds `events:courier` (dispatch's own aggregate stream —
ADR 0007 §4): `cg:order-sync` now runs as two processes, one per stream,
same group name, same handler — a Redis consumer group is scoped to a
single stream, so this is a second `stream_consumer` invocation
(`consumer-order-sync-courier` in compose.yaml), not a second group.

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
from front_of_house.eventing.handlers import HANDLERS
from front_of_house.eventing.redis_client import get_redis_client

DEFAULT_STREAM = "events:order"


class Command(BaseCommand):
    help = "Run one consumer group's XREADGROUP loop against one stream."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--group", required=True, choices=sorted(HANDLERS))
        parser.add_argument("--stream", default=DEFAULT_STREAM)
        parser.add_argument("--consumer-name", default=None)

    def handle(
        self,
        *_args: Any,
        group: str,
        stream: str,
        consumer_name: str | None,
        **_options: Any,
    ) -> None:
        handler = HANDLERS[group]
        consumer = consumer_name or f"{socket.gethostname()}-{group}-{stream}"
        client = get_redis_client()
        config = load_config()

        ensure_group(client, stream, group)
        self.stdout.write(
            self.style.SUCCESS(f"stream_consumer[{group}]: consuming {stream} as {consumer}")
        )

        while True:
            reclaimed = autoclaim(
                client,
                stream,
                group,
                consumer,
                min_idle_ms=config.streams.claim_min_idle_seconds * 1000,
                count=config.streams.read_count,
            )
            fresh = read_batch(
                client,
                stream,
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
                ack(client, stream, group, [message.message_id])
