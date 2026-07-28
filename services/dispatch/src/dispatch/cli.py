"""CLI entrypoints for dispatch's event-spine processes.

No Django here, so a plain argparse script stands in for `manage.py relay`
/ `manage.py stream_consumer`, same as kitchen's `cli.py` (ADR 0003).
"""

import argparse
import math
import socket
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import psycopg
from sqlalchemy.orm import Session

from dinner_rush_core.config import load_config
from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.outbox import relay_batch
from dinner_rush_core.streams import ack, autoclaim, ensure_group, read_batch
from dinner_rush_core.streams import publish as stream_publish
from dispatch import settings
from dispatch.consumers import HANDLERS
from dispatch.db import SessionLocal
from dispatch.dbapi import raw_cursor
from dispatch.geo import set_position
from dispatch.models import Courier
from dispatch.redis_client import get_redis_client
from dispatch.writer import OUTBOX_NOTIFY_CHANNEL

STREAM = "events:order"  # dispatch's own consumer group only reads this one


def run_stream_consumer(group: str, consumer_name: str | None = None) -> None:
    handler: Callable[[Session, EventEnvelope], None] = HANDLERS[group]
    consumer = consumer_name or f"{socket.gethostname()}-{group}"
    client = get_redis_client()
    config = load_config()

    ensure_group(client, STREAM, group)
    print(f"stream_consumer[{group}]: consuming as {consumer}", flush=True)

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
            session = SessionLocal()
            try:
                handler(session, message.envelope)
            except Exception as exc:
                print(f"stream_consumer[{group}]: error, will retry — {exc}", file=sys.stderr)
                session.rollback()
                continue
            finally:
                session.close()
            ack(client, STREAM, group, [message.message_id])


def run_relay() -> None:
    config = load_config()
    redis_client = get_redis_client()
    poll_seconds = config.streams.outbox_poll_ms / 1000

    listen_conn = psycopg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        autocommit=True,
    )
    with listen_conn.cursor() as cursor:
        cursor.execute(f"LISTEN {OUTBOX_NOTIFY_CHANNEL}")

    print("relay: listening for outbox rows", flush=True)
    while True:
        try:
            _relay_once(redis_client, config.streams.maxlen)
        except Exception as exc:
            print(f"relay: error, will retry — {exc}", file=sys.stderr)
        for _ in listen_conn.notifies(timeout=poll_seconds):
            break  # a NOTIFY arrived early — relay again immediately


def _relay_once(redis_client: Any, maxlen: int) -> None:
    def _publish(row: Any) -> None:
        stream_publish(redis_client, row.stream, row.envelope, maxlen=maxlen)

    session = SessionLocal()
    try:
        count = relay_batch(raw_cursor(session), _publish, limit=100)
        session.commit()
    finally:
        session.close()
    if count:
        print(f"relay: published {count} event(s)", flush=True)


def run_seed() -> None:
    """`courier_count` couriers from `config.yaml`'s `dispatch:` block,
    alternating vehicle type, seeded `idle` with a starting position
    scattered near the restaurant (within `search_radius_cells`) so
    assignment has candidates the moment the first order goes `ready` —
    there's no simulator-driven courier actor to bring them online instead
    (ADR 0007 §6). Idempotent: does nothing if any couriers already exist,
    matching kitchen's own seed command."""
    config = load_config()
    session = SessionLocal()
    redis_client = get_redis_client()
    try:
        if session.query(Courier).count() > 0:
            print("seed: dispatch already seeded, skipping", flush=True)
            return
        vehicles = ("bike", "scooter")
        speeds = config.dispatch.courier_speed_cells_per_minute
        restaurant = config.dispatch.restaurant
        radius = config.dispatch.search_radius_cells
        for i in range(config.dispatch.courier_count):
            vehicle = vehicles[i % len(vehicles)]
            speed = speeds.bike if vehicle == "bike" else speeds.scooter
            courier = Courier(
                name=f"Courier {i + 1}",
                status="idle",
                vehicle=vehicle,
                speed_cells_per_min=speed,
                shift_started_at=datetime.now(UTC),
            )
            session.add(courier)
            session.flush()  # need courier.id for its starting position
            angle = 2 * math.pi * i / max(config.dispatch.courier_count, 1)
            scatter = radius / 2
            grid_width, grid_height = config.dispatch.grid.width, config.dispatch.grid.height
            x = max(0, min(grid_width, round(restaurant.x + scatter * math.cos(angle))))
            y = max(0, min(grid_height, round(restaurant.y + scatter * math.sin(angle))))
            set_position(redis_client, str(courier.id), x, y)
        session.commit()
        print(f"seeded {config.dispatch.courier_count} couriers", flush=True)
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="dispatch.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("relay")
    sub.add_parser("seed")

    consumer_parser = sub.add_parser("stream_consumer")
    consumer_parser.add_argument("--group", required=True, choices=sorted(HANDLERS))
    consumer_parser.add_argument("--consumer-name", default=None)

    args = parser.parse_args()
    if args.command == "relay":
        run_relay()
    elif args.command == "seed":
        run_seed()
    else:
        run_stream_consumer(args.group, args.consumer_name)


if __name__ == "__main__":
    main()
