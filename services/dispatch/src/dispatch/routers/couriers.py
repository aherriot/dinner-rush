import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from dinner_rush_core.auth import Claims
from dinner_rush_core.config import load_config
from dispatch.api_models import CourierOut, CourierPositionRequest, CourierStatusRequest, TripOut
from dispatch.auth import require_courier, require_service_scope
from dispatch.db import get_session
from dispatch.geo import get_position, get_positions, set_position
from dispatch.models import Courier, Trip
from dispatch.redis_client import get_redis_client
from dispatch.tasks import handle_courier_offline
from dispatch.writer import build_envelope, write_outbox_event

board_router = APIRouter(dependencies=[Depends(require_service_scope("dispatch:read"))])
courier_router = APIRouter(dependencies=[Depends(require_courier)])


def _own_courier_or_403(courier_id: uuid.UUID, claims: Claims) -> None:
    if claims.sub != str(courier_id):
        raise HTTPException(status_code=403, detail="token does not authorize this courier")


@board_router.get("/couriers", response_model=list[CourierOut])
def list_couriers(session: Session = Depends(get_session)) -> list[CourierOut]:
    """`GET /couriers` (SPEC.md §3.4) — status/metadata from Postgres, current
    position from Redis, merged into one board-friendly shape."""
    couriers = list(session.execute(select(Courier)).scalars().all())
    positions = get_positions(get_redis_client(), [str(c.id) for c in couriers])

    def _out(courier: Courier) -> CourierOut:
        position = positions.get(str(courier.id))
        x, y = position if position is not None else (None, None)
        return CourierOut(
            id=courier.id,
            name=courier.name,
            status=courier.status,
            vehicle=courier.vehicle,
            speed_cells_per_min=courier.speed_cells_per_min,
            shift_started_at=courier.shift_started_at,
            x=x,
            y=y,
        )

    return [_out(c) for c in couriers]


@courier_router.post("/couriers/{courier_id}/status", response_model=CourierOut)
def set_courier_status(
    courier_id: uuid.UUID,
    request: CourierStatusRequest,
    claims: Claims = Depends(require_courier),
    session: Session = Depends(get_session),
) -> Courier:
    _own_courier_or_403(courier_id, claims)
    if request.status not in ("online", "offline"):
        raise HTTPException(status_code=422, detail="status must be 'online' or 'offline'")

    courier = session.get(Courier, courier_id)
    if courier is None:
        raise HTTPException(status_code=404, detail="courier not found")

    now = datetime.now(UTC)

    if request.status == "offline":
        x, y = get_position(get_redis_client(), str(courier_id)) or (0, 0)
        handle_courier_offline(session, courier)
        event_type = "courier.offline"
    else:
        if courier.status == "offline":
            # Coming back online is this simulation's stand-in for "showed
            # up at the restaurant to start a shift" (it's also the moment
            # `shift_started_at` gets set, below) — so it snaps position back
            # to base the same way `_release_courier_if_idle`
            # (`routers/trips.py`) and `arrive_at_dropoff`
            # (`dispatch.tasks`) already do for every other path that
            # releases a courier to idle. Without this, a courier taken
            # offline mid-trip resumes idle wherever `handle_courier_offline`
            # left them — outside `attempt_assignment`'s `GEOSEARCH` radius,
            # same failure mode, different trigger.
            courier.status = "idle"
            restaurant = load_config().dispatch.restaurant
            set_position(get_redis_client(), str(courier_id), restaurant.x, restaurant.y)
            x, y = restaurant.x, restaurant.y
        else:
            x, y = get_position(get_redis_client(), str(courier_id)) or (0, 0)
        if courier.shift_started_at is None:
            courier.shift_started_at = now
        event_type = "courier.online"

    envelope = build_envelope(
        event_type=event_type,
        aggregate_type="courier",
        aggregate_id=courier.id,
        sequence=int(now.timestamp() * 1000),
        correlation_id=courier.id,
        payload={"courier_id": str(courier.id), "x": x, "y": y},
    )
    write_outbox_event(session, envelope)
    session.commit()
    return courier


@courier_router.post("/couriers/{courier_id}/position", response_model=CourierOut)
def set_courier_position(
    courier_id: uuid.UUID,
    request: CourierPositionRequest,
    claims: Claims = Depends(require_courier),
    session: Session = Depends(get_session),
) -> Courier:
    _own_courier_or_403(courier_id, claims)
    courier = session.get(Courier, courier_id)
    if courier is None:
        raise HTTPException(status_code=404, detail="courier not found")
    set_position(get_redis_client(), str(courier_id), request.x, request.y)
    return courier


@courier_router.get("/couriers/me/trips", response_model=list[TripOut])
def my_trips(
    claims: Claims = Depends(require_courier), session: Session = Depends(get_session)
) -> list[Trip]:
    stmt = (
        select(Trip)
        .where(Trip.courier_id == uuid.UUID(claims.sub))
        .order_by(Trip.assigned_at.desc())
    )
    return list(session.execute(stmt).scalars().all())
