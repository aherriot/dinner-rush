"""Trip lifecycle + the time-boxed address grant (SPEC.md §3.4, §6.2).

`GET /trips/{id}/dropoff` is the one endpoint with its own test file
(`tests/test_address_grant.py`) — the four cases SPEC.md §6.2 requires:
before assignment, during, after delivery, and after `expires_at` with the
trip still open. The check is exactly the query in the spec: `courier_id`
matches, `revoked_at IS NULL`, `expires_at > now()`.

`POST /trips/{id}/pickup` performs *both* `pick_up` and `depart`
(SPEC.md §2's FSM has both, but §3.4's API surface lists only `/pickup` and
`/deliver` — courier confirms arrival and immediately starts driving in one
call). This mirrors exactly what the autopilot in `dispatch.tasks` does on a
timer; a real courier client calling these endpoints by hand and the
autopilot calling the same transitions automatically are two callers of the
same state machine, not two different ones (ADR 0007 §6).
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dinner_rush_core.auth import Claims
from dispatch.api_models import BacklogOut, DropoffOut, TripFailRequest, TripOut
from dispatch.auth import require_courier, require_service_scope
from dispatch.db import get_session
from dispatch.fsm import IllegalTransition, apply_transition
from dispatch.geo import set_position
from dispatch.models import AddressGrant, Courier, PendingDropoff, Trip
from dispatch.redis_client import get_redis_client
from dispatch.writer import build_envelope, write_outbox_event

_ACTIVE_TRIP_STATUSES = ("assigned", "picked_up", "delivering")

board_router = APIRouter(dependencies=[Depends(require_service_scope("dispatch:read"))])
courier_router = APIRouter(dependencies=[Depends(require_courier)])


def _get_trip_or_404(session: Session, trip_id: uuid.UUID) -> Trip:
    trip = session.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="trip not found")
    return trip


def _own_trip_or_403(trip: Trip, claims: Claims) -> None:
    if claims.sub != str(trip.courier_id):
        raise HTTPException(status_code=403, detail="token does not authorize this trip")


@board_router.get("/trips", response_model=list[TripOut])
def list_trips(session: Session = Depends(get_session)) -> list[Trip]:
    stmt = select(Trip).where(Trip.status.in_(_ACTIVE_TRIP_STATUSES)).order_by(Trip.assigned_at)
    return list(session.execute(stmt).scalars().all())


@board_router.get("/backlog", response_model=BacklogOut)
def get_backlog(session: Session = Depends(get_session)) -> BacklogOut:
    """Orders `dispatch.tasks.assign_order` hasn't matched to a courier yet
    — but only counting from `ready_at`, not `created_at`: a `pending_dropoff`
    row exists from `order.placed` onward (ADR 0007 §1), long before the
    order is actually ready, so counting every surviving row would fold in
    everything still queued/prepping/baking too. `ready_at` is set once
    `order.ready` actually arrives (`consumers.py`); a row that outlives
    assignment after that means the retry loop keeps failing to find a
    courier — the row is only ever deleted on a successful
    `attempt_assignment` (`dispatch.tasks.assign_order`). The `NOT EXISTS`
    against `trip` is belt-and-suspenders for that invariant rather than the
    primary signal: every surviving `pending_dropoff` row already implies no
    trip exists for its `order_id`."""
    is_ready = PendingDropoff.ready_at.is_not(None)
    no_trip_yet = ~select(Trip.id).where(Trip.order_id == PendingDropoff.order_id).exists()
    stmt = select(func.count(), func.min(PendingDropoff.ready_at)).where(is_ready, no_trip_yet)
    ready_count, oldest_ready_at = session.execute(stmt).one()

    oldest_waiting_seconds = None
    if oldest_ready_at is not None:
        oldest_waiting_seconds = (datetime.now(UTC) - _as_utc(oldest_ready_at)).total_seconds()

    return BacklogOut(ready_count=ready_count, oldest_waiting_seconds=oldest_waiting_seconds)


def _as_utc(value: datetime) -> datetime:
    """`pending_dropoff.created_at` is a naive-on-disk "timestamp without
    time zone" column this codebase only ever writes `datetime.now(UTC)`
    into — naive-but-really-UTC once round-tripped through Postgres (same
    reasoning as `kitchen.reconcile._as_utc`)."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@courier_router.get("/trips/{trip_id}/dropoff", response_model=DropoffOut)
def get_dropoff(
    trip_id: uuid.UUID,
    claims: Claims = Depends(require_courier),
    session: Session = Depends(get_session),
) -> AddressGrant:
    """SPEC.md §6.2, verbatim: `courier_id` matches AND `revoked_at IS NULL`
    AND `expires_at > now()`. Any other case — no grant row, wrong courier,
    revoked, or simply expired — is a 403, not a 404: this endpoint never
    confirms or denies that the trip exists to a courier who isn't
    (currently) entitled to see it."""
    stmt = select(AddressGrant).where(
        AddressGrant.trip_id == trip_id,
        AddressGrant.courier_id == uuid.UUID(claims.sub),
        AddressGrant.revoked_at.is_(None),
        AddressGrant.expires_at > datetime.now(UTC),
    )
    grant = session.execute(stmt).scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=403, detail="no live address grant for this trip")
    return grant


@courier_router.post("/trips/{trip_id}/pickup", response_model=TripOut)
def pick_up_trip(
    trip_id: uuid.UUID,
    claims: Claims = Depends(require_courier),
    session: Session = Depends(get_session),
) -> Trip:
    trip = _get_trip_or_404(session, trip_id)
    _own_trip_or_403(trip, claims)
    now = datetime.now(UTC)
    sequence = int(now.timestamp() * 1000)

    try:
        trip.status = apply_transition(trip.status, "pick_up")
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    trip.picked_up_at = now
    picked_up_envelope = build_envelope(
        event_type="order.picked_up",
        aggregate_type="order",
        aggregate_id=trip.order_id,
        sequence=sequence,
        correlation_id=trip.order_id,
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

    session.commit()
    return trip


@courier_router.post("/trips/{trip_id}/deliver", response_model=TripOut)
def deliver_trip(
    trip_id: uuid.UUID,
    claims: Claims = Depends(require_courier),
    session: Session = Depends(get_session),
) -> Trip:
    trip = _get_trip_or_404(session, trip_id)
    _own_trip_or_403(trip, claims)
    now = datetime.now(UTC)

    try:
        trip.status = apply_transition(trip.status, "deliver")
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    trip.delivered_at = now
    _revoke_grant(session, trip.id, now)
    _release_courier_if_idle(session, trip)
    set_position(get_redis_client(), str(trip.courier_id), trip.dropoff_x, trip.dropoff_y)

    envelope = build_envelope(
        event_type="order.delivered",
        aggregate_type="order",
        aggregate_id=trip.order_id,
        sequence=int(now.timestamp() * 1000),
        correlation_id=trip.order_id,
        payload={
            "code": trip.code,
            "courier_id": str(trip.courier_id),
            "total_elapsed_s": (now - trip.assigned_at).total_seconds(),
        },
    )
    write_outbox_event(session, envelope)
    session.commit()
    return trip


@courier_router.post("/trips/{trip_id}/fail", response_model=TripOut)
def fail_trip(
    trip_id: uuid.UUID,
    request: TripFailRequest,
    claims: Claims = Depends(require_courier),
    session: Session = Depends(get_session),
) -> Trip:
    trip = _get_trip_or_404(session, trip_id)
    _own_trip_or_403(trip, claims)
    now = datetime.now(UTC)

    try:
        trip.status = apply_transition(trip.status, "fail")
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    trip.failed_at = now
    trip.failure_reason = request.reason
    _revoke_grant(session, trip.id, now)
    _release_courier_if_idle(session, trip)

    envelope = build_envelope(
        event_type="order.failed",
        aggregate_type="order",
        aggregate_id=trip.order_id,
        sequence=int(now.timestamp() * 1000),
        correlation_id=trip.order_id,
        payload={"code": trip.code, "reason": request.reason},
    )
    write_outbox_event(session, envelope)
    session.commit()
    return trip


def _revoke_grant(session: Session, trip_id: uuid.UUID, now: datetime) -> None:
    grant = session.execute(
        select(AddressGrant).where(
            AddressGrant.trip_id == trip_id, AddressGrant.revoked_at.is_(None)
        )
    ).scalar_one_or_none()
    if grant is not None:
        grant.revoked_at = now


def _release_courier_if_idle(session: Session, trip: Trip) -> None:
    other_active = session.execute(
        select(func.count())
        .select_from(Trip)
        .where(
            Trip.courier_id == trip.courier_id,
            Trip.id != trip.id,
            Trip.status.in_(_ACTIVE_TRIP_STATUSES),
        )
    ).scalar_one()
    if other_active == 0:
        courier = session.get(Courier, trip.courier_id)
        assert courier is not None
        courier.status = "idle"
