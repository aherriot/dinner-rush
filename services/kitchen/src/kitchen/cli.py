"""CLI entrypoints for kitchen's event-spine processes.

No Django here, so a plain argparse script stands in for `manage.py relay`
/ `manage.py stream_consumer` — same loops, same `dinner_rush_core` helpers,
reused unmodified (ADR 0003).
"""

import argparse
import socket
import sys
import time
from collections.abc import Callable
from typing import Any

import psycopg
from sqlalchemy import text
from sqlalchemy.orm import Session

from dinner_rush_core.config import load_config
from dinner_rush_core.events.envelope import EventEnvelope
from dinner_rush_core.outbox import relay_batch
from dinner_rush_core.streams import ack, autoclaim, ensure_group, read_batch
from dinner_rush_core.streams import publish as stream_publish
from kitchen import settings
from kitchen.consumers import HANDLERS
from kitchen.db import SessionLocal
from kitchen.dbapi import raw_cursor
from kitchen.models import Oven, OvenSlot, Station
from kitchen.reconcile import reconcile_stuck_tickets
from kitchen.redis_client import get_redis_client
from kitchen.slots import reap_stuck_slots
from kitchen.speed import get_speed
from kitchen.writer import OUTBOX_NOTIFY_CHANNEL

STREAM = "events:order"  # kitchen only consumes order.accepted off this stream


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
    """Ovens and stations from `config.yaml`'s `kitchen:` block. Idempotent:
    does nothing if any ovens already exist, matching `make seed`'s
    re-runnable contract on the gateway side."""
    config = load_config()
    session = SessionLocal()
    try:
        if session.query(Oven).count() > 0:
            print("seed: kitchen already seeded, skipping", flush=True)
            return
        for oven in config.kitchen.ovens:
            row = Oven(name=oven.name, slot_count=oven.slot_count, status="available")
            session.add(row)
            session.flush()  # need row.id before creating its slots
            for slot_index in range(oven.slot_count):
                session.add(OvenSlot(oven_id=row.id, slot_index=slot_index))
        for station in config.kitchen.stations:
            session.add(
                Station(
                    name=station.name,
                    kind=station.kind,
                    capacity=station.capacity,
                    status="available",
                )
            )
        session.commit()
        print(
            f"seeded {len(config.kitchen.ovens)} ovens, "
            f"{len(config.kitchen.stations)} stations",
            flush=True,
        )
    finally:
        session.close()


def run_reset() -> None:
    """`make reset`'s kitchen half: clears tickets and the event spine, and
    un-claims every oven slot / restores oven and station status to
    `available` — so a `chaos_scenario oven_down` left active doesn't survive
    the reset. Ovens, slots and stations themselves are `seed`'s fixtures and
    stay put; this only clears what a demo run accumulated on top of them."""
    session = SessionLocal()
    try:
        session.execute(
            text("TRUNCATE TABLE ticket, outbox, processed_event RESTART IDENTITY CASCADE")
        )
        session.query(OvenSlot).update({"order_id": None, "claimed_at": None, "frees_at": None})
        session.query(Oven).update({"status": "available", "event_sequence": 0})
        session.query(Station).update({"status": "available"})
        session.commit()
        print("reset: tickets and event spine cleared, oven slots un-claimed", flush=True)
    finally:
        session.close()


def run_reap() -> None:
    """The kitchen's crash-safety sweep — `slots.reap_stuck_slots` (a stuck
    oven-slot claim outliving its own `frees_at`) and
    `reconcile.reconcile_stuck_tickets` (a ticket whose next Celery step was
    lost) were each written as idempotent, standalone functions but never
    actually run anywhere; this loop is what closes that gap, on
    `slot_reaper_interval_seconds`'s cadence for both."""
    config = load_config()
    interval = config.kitchen.slot_reaper_interval_seconds
    slot_grace = config.kitchen.slot_reaper_grace_seconds
    ticket_grace = config.kitchen.ticket_reconciler_grace_seconds

    print(
        f"reap: sweeping every {interval}s "
        f"(slot grace {slot_grace}s, ticket grace {ticket_grace}s)",
        flush=True,
    )
    while True:
        session = SessionLocal()
        try:
            freed = reap_stuck_slots(session, slot_grace)
            reconciled = reconcile_stuck_tickets(
                session, grace_seconds=ticket_grace, speed=get_speed()
            )
            session.commit()
        except Exception as exc:
            print(f"reap: error, will retry — {exc}", file=sys.stderr)
            session.rollback()
            freed, reconciled = [], []
        finally:
            session.close()
        if freed:
            print(f"reap: reclaimed {len(freed)} stuck oven slot(s)", flush=True)
        if reconciled:
            codes = ", ".join(t.code for t in reconciled)
            print(f"reap: resumed {len(reconciled)} stuck ticket(s) — {codes}", flush=True)
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(prog="kitchen.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("relay")
    sub.add_parser("seed")
    sub.add_parser("reset")
    sub.add_parser("reap")

    consumer_parser = sub.add_parser("stream_consumer")
    consumer_parser.add_argument("--group", required=True, choices=sorted(HANDLERS))
    consumer_parser.add_argument("--consumer-name", default=None)

    args = parser.parse_args()
    if args.command == "relay":
        run_relay()
    elif args.command == "seed":
        run_seed()
    elif args.command == "reset":
        run_reset()
    elif args.command == "reap":
        run_reap()
    else:
        run_stream_consumer(args.group, args.consumer_name)


if __name__ == "__main__":
    main()
