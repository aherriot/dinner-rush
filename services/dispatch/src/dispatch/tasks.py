"""Celery-scheduled work: the assignment retry loop and the courier motion
autopilot (ADR 0007 §2, §6).

Real transitions, real timers, `SPEED`-scaled at the point each step is
scheduled (SPEC.md §5) — the autopilot calls exactly the same
`dispatch.fsm`/model updates the authenticated HTTP endpoints in
`dispatch.routers.trips` would if a real courier client called them instead.
"""

from datetime import UTC, datetime
from uuid import UUID

from celery import shared_task
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from dinner_rush_core.config import load_config
from dispatch.assignment import attempt_assignment
from dispatch.celery_app import app  # noqa: F401 - registers this module's tasks
from dispatch.db import SessionLocal
from dispatch.fsm import apply_transition, is_terminal
from dispatch.geo import set_position
from dispatch.models import AddressGrant, Courier, PendingDropoff, Trip
from dispatch.redis_client import get_redis_client
from dispatch.speed import get_speed as _speed
from dispatch.writer import build_envelope, write_outbox_event

_ACTIVE_TRIP_STATUSES = ("assigned", "picked_up", "delivering")


def try_assign(
    *,
    order_id: UUID,
    code: str,
    dropoff_x: int,
    dropoff_y: int,
    line1: str,
    sequence: int,
    causation_id: str,
) -> None:
    """Kick off an assignment attempt for `order_id` right away — called
    from `dispatch.consumers` when `order.ready` arrives."""
    assign_order.apply_async(
        args=(str(order_id), code, dropoff_x, dropoff_y, line1, sequence, causation_id, 0)
    )


@shared_task(name="dispatch.assign_order")
def assign_order(
    order_id: str,
    code: str,
    dropoff_x: int,
    dropoff_y: int,
    line1: str,
    sequence: int,
    causation_id: str | None,
    attempt: int = 0,
) -> None:
    config = load_config().dispatch
    speed = _speed()
    redis_client = get_redis_client()

    session = SessionLocal()
    try:
        result = attempt_assignment(
            session,
            redis_client,
            order_id=UUID(order_id),
            code=code,
            dropoff_x=dropoff_x,
            dropoff_y=dropoff_y,
            line1=line1,
            config=config,
            speed=speed,
        )
        if result is None:
            session.rollback()
            # Capped exponential backoff, not the flat `assignment_retry_seconds`
            # cadence — a permanently-unassignable order retrying every ~1s
            # (scaled by SPEED) was observed to flood the worker badly enough
            # that already-assigned trips' own scheduled ETA tasks
            # (`arrive_at_pickup`/`arrive_at_dropoff`) starved and never ran,
            # so couriers never returned to idle. attempt=0 keeps today's
            # prompt retry for the common case (a courier frees up in the
            # next few seconds); each subsequent miss doubles the wait, up to
            # `max_assignment_retry_seconds`.
            backoff_seconds = min(
                config.assignment_retry_seconds * (2**attempt),
                config.max_assignment_retry_seconds,
            )
            assign_order.apply_async(
                args=(
                    order_id,
                    code,
                    dropoff_x,
                    dropoff_y,
                    line1,
                    sequence,
                    causation_id,
                    attempt + 1,
                ),
                countdown=backoff_seconds / speed,
            )
            return

        pending = session.get(PendingDropoff, UUID(order_id))
        if pending is not None:
            session.delete(pending)

        envelope = build_envelope(
            event_type="courier.assigned",
            aggregate_type="courier",
            aggregate_id=result.courier_id,  # type: ignore[arg-type]
            sequence=sequence,
            correlation_id=UUID(order_id),
            causation_id=UUID(causation_id) if causation_id else None,
            payload={
                "code": code,
                "courier_id": str(result.courier_id),
                "eta_at": result.eta_at,
                "distance_cells": result.distance_cells,
            },
        )
        write_outbox_event(session, envelope)
        session.commit()
    finally:
        session.close()

    cells_per_second = result.speed_cells_per_min / 60.0 / speed
    pickup_leg_seconds = result.pickup_leg_cells / cells_per_second if cells_per_second else 0.0

    _tick_motion.apply_async(
        args=(
            str(result.courier_id),
            result.from_x,
            result.from_y,
            config.restaurant.x,
            config.restaurant.y,
            datetime.now(UTC).isoformat(),
            pickup_leg_seconds,
        )
    )
    arrive_at_pickup.apply_async(
        args=(str(result.trip_id), sequence + 1, str(envelope.event_id)),
        countdown=pickup_leg_seconds,
    )


@shared_task(name="dispatch.tick_motion")
def _tick_motion(
    courier_id: str,
    from_x: int,
    from_y: int,
    to_x: int,
    to_y: int,
    started_at_iso: str,
    duration_seconds: float,
) -> None:
    """Best-effort visual position interpolation (ADR 0007 §6) — never gates
    a real state transition; those are scheduled on their own timers below.
    Keyed by `courier_id` (not the trip) since that's what `GET /couriers`
    and `attempt_assignment`'s `GEOSEARCH` both look positions up by."""
    started_at = datetime.fromisoformat(started_at_iso)
    elapsed = (datetime.now(UTC) - started_at).total_seconds()
    fraction = 1.0 if duration_seconds <= 0 else min(1.0, max(0.0, elapsed / duration_seconds))

    redis_client = get_redis_client()
    x = round(from_x + (to_x - from_x) * fraction)
    y = round(from_y + (to_y - from_y) * fraction)
    set_position(redis_client, courier_id, x, y)

    if fraction >= 1.0:
        return
    config = load_config().dispatch
    tick_seconds = min(config.eta_recalc_interval_seconds / _speed(), duration_seconds - elapsed)
    _tick_motion.apply_async(
        args=(courier_id, from_x, from_y, to_x, to_y, started_at_iso, duration_seconds),
        countdown=max(tick_seconds, 0.1),
    )


@shared_task(name="dispatch.arrive_at_pickup")
def arrive_at_pickup(trip_id: str, sequence: int, causation_id: str | None) -> None:
    session = SessionLocal()
    try:
        trip = session.get(Trip, UUID(trip_id))
        if trip is None or is_terminal(trip.status):
            return
        now = datetime.now(UTC)

        trip.status = apply_transition(trip.status, "pick_up")
        trip.picked_up_at = now
        picked_up_envelope = build_envelope(
            event_type="order.picked_up",
            aggregate_type="order",
            aggregate_id=trip.order_id,
            sequence=sequence,
            correlation_id=trip.order_id,
            causation_id=UUID(causation_id) if causation_id else None,
            payload={"code": trip.code, "courier_id": str(trip.courier_id), "at": now},
        )
        write_outbox_event(session, picked_up_envelope)

        trip.status = apply_transition(trip.status, "depart")
        delivering_envelope = build_envelope(
            event_type="order.delivering",
            aggregate_type="order",
            aggregate_id=trip.order_id,
            sequence=sequence + 1,
            correlation_id=trip.order_id,
            causation_id=picked_up_envelope.event_id,
            payload={"code": trip.code, "courier_id": str(trip.courier_id), "eta_at": trip.eta_at},
        )
        write_outbox_event(session, delivering_envelope)

        courier = session.get(Courier, trip.courier_id)
        assert courier is not None
        courier.status = "delivering"

        pickup_x, pickup_y, dropoff_x, dropoff_y = (
            trip.pickup_x,
            trip.pickup_y,
            trip.dropoff_x,
            trip.dropoff_y,
        )
        courier_id = str(trip.courier_id)
        eta_at = trip.eta_at
        next_sequence = sequence + 2
        next_causation = str(delivering_envelope.event_id)
        session.commit()
    finally:
        session.close()

    dropoff_leg_seconds = max((eta_at - now).total_seconds(), 0.0)
    _tick_motion.apply_async(
        args=(
            courier_id,
            pickup_x,
            pickup_y,
            dropoff_x,
            dropoff_y,
            now.isoformat(),
            dropoff_leg_seconds,
        )
    )
    arrive_at_dropoff.apply_async(
        args=(trip_id, next_sequence, next_causation), countdown=dropoff_leg_seconds
    )


@shared_task(name="dispatch.arrive_at_dropoff")
def arrive_at_dropoff(trip_id: str, sequence: int, causation_id: str | None) -> None:
    session = SessionLocal()
    try:
        trip = session.get(Trip, UUID(trip_id))
        if trip is None or is_terminal(trip.status):
            return
        now = datetime.now(UTC)

        trip.status = apply_transition(trip.status, "deliver")
        trip.delivered_at = now

        grant = session.execute(
            _active_grant_stmt(trip.id)
        ).scalar_one_or_none()
        if grant is not None:
            grant.revoked_at = now

        courier = session.get(Courier, trip.courier_id)
        assert courier is not None
        other_active = session.execute(
            _other_active_trips_stmt(courier.id, trip.id)
        ).scalar_one()
        if other_active == 0:
            # Idle couriers head back to base rather than parking at the
            # dropoff — `attempt_assignment` only ever searches for idle
            # couriers within `search_radius_cells` of the restaurant
            # (`assignment.py`), and every pickup is at that same fixed
            # point, so a courier left idle out at a dropoff on the far side
            # of the grid would never again be found by that search: it's
            # not a temporary miss, it's permanent until the courier goes
            # offline/online. Snapping back to base keeps the radius search
            # meaningful instead of quietly stranding couriers.
            courier.status = "idle"
            config = load_config().dispatch
            set_position(
                get_redis_client(), str(courier.id), config.restaurant.x, config.restaurant.y
            )
        else:
            set_position(get_redis_client(), str(courier.id), trip.dropoff_x, trip.dropoff_y)

        envelope = build_envelope(
            event_type="order.delivered",
            aggregate_type="order",
            aggregate_id=trip.order_id,
            sequence=sequence,
            correlation_id=trip.order_id,
            causation_id=UUID(causation_id) if causation_id else None,
            payload={
                "code": trip.code,
                "courier_id": str(trip.courier_id),
                "total_elapsed_s": (now - trip.assigned_at).total_seconds(),
            },
        )
        write_outbox_event(session, envelope)
        session.commit()
    finally:
        session.close()


def _active_grant_stmt(trip_id: object) -> Select[tuple[AddressGrant]]:
    return select(AddressGrant).where(
        AddressGrant.trip_id == trip_id, AddressGrant.revoked_at.is_(None)
    )


def _other_active_trips_stmt(courier_id: object, exclude_trip_id: object) -> Select[tuple[int]]:
    return (
        select(func.count())
        .select_from(Trip)
        .where(
            Trip.courier_id == courier_id,
            Trip.id != exclude_trip_id,
            Trip.status.in_(_ACTIVE_TRIP_STATUSES),
        )
    )


def handle_courier_offline(session: Session, courier: Courier) -> None:
    """`POST /couriers/{id}/status {"offline"}` mid-trip (ADR 0007 §4): every
    active trip this courier is running gets unassigned and its address
    grant revoked, then reassignment is re-attempted from scratch using the
    same dropoff data (still on the trip row) — the courier-offline chaos
    scenario in `config.yaml`."""
    active_trips = (
        session.execute(
            select(Trip).where(
                Trip.courier_id == courier.id, Trip.status.in_(("assigned", "picked_up"))
            )
        )
        .scalars()
        .all()
    )

    for trip in active_trips:
        now = datetime.now(UTC)
        # Not chained from a consumed envelope's `sequence` (this path starts
        # from an HTTP call, not a stream message) — a wall-clock-derived
        # value is monotonic enough for a rare, low-frequency event; nothing
        # depends on strict per-aggregate ordering here.
        pseudo_sequence = int(now.timestamp() * 1000)
        grant = session.execute(_active_grant_stmt(trip.id)).scalar_one_or_none()
        line1 = grant.line1 if grant is not None else ""
        if grant is not None:
            grant.revoked_at = now
        trip.status = apply_transition(trip.status, "unassign")

        envelope = build_envelope(
            event_type="order.unassigned",
            aggregate_type="order",
            aggregate_id=trip.order_id,
            sequence=pseudo_sequence,
            correlation_id=trip.order_id,
            payload={"code": trip.code, "previous_courier_id": str(courier.id)},
        )
        write_outbox_event(session, envelope)
        session.flush()

        try_assign(
            order_id=trip.order_id,
            code=trip.code,
            dropoff_x=trip.dropoff_x,
            dropoff_y=trip.dropoff_y,
            line1=line1,
            sequence=pseudo_sequence + 1,
            causation_id=str(envelope.event_id),
        )

    courier.status = "offline"
