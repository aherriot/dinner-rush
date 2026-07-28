"""Courier assignment (SPEC.md §3.4, §5) — nearest available courier, a
light trip-batching heuristic, and the ETA/distance math the pricing formula
and `courier.assigned` payload both need.

An idle courier within `search_radius_cells` is always preferred over
batching onto a busy one, even when the busy courier's detour is objectively
cheaper — leaving a courier idle while orders wait is worse for the
operation than a slightly longer trip. Batching (ADR 0007 §3) is a fallback
for when no idle courier is in range: a courier already
`assigned`/`delivering` with spare capacity (`max_trips_per_courier`) picks
up the new order too, as long as diverting to the new pickup costs no more
than `batch_max_detour_cells` — real multi-stop routing is out of scope (ADR
0007 §3, CLAUDE.md §2's "timebox everything else hard").
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dinner_rush_core.config import DispatchConfig
from dispatch.geo import chebyshev, get_position, nearest_within_radius
from dispatch.models import AddressGrant, Courier, Trip

if TYPE_CHECKING:
    from redis import Redis

_ACTIVE_TRIP_STATUSES = ("assigned", "picked_up", "delivering")


@dataclass(frozen=True)
class Assignment:
    trip_id: object
    courier_id: object
    eta_at: datetime
    distance_cells: int
    # The two legs of the journey, split out for `dispatch.tasks`' autopilot
    # to schedule pickup/dropoff arrival separately — not persisted (only
    # `distance_cells`, the total, is a SPEC.md §1.3 column).
    from_x: int
    from_y: int
    pickup_leg_cells: int
    dropoff_leg_cells: int
    speed_cells_per_min: float


def _speed_cells_per_second(courier: Courier) -> float:
    return float(courier.speed_cells_per_min) / 60.0


def _batch_candidate(
    session: Session, redis_client: "Redis", pickup_x: int, pickup_y: int, config: DispatchConfig
) -> tuple[Courier, int] | None:
    """The busy-but-has-room courier with the smallest detour to swing back
    to the restaurant, if any is within `batch_max_detour_cells`."""
    active_counts = (
        select(Trip.courier_id, func.count().label("active"))
        .where(Trip.status.in_(_ACTIVE_TRIP_STATUSES))
        .group_by(Trip.courier_id)
        .subquery()
    )
    stmt = (
        select(Courier, active_counts.c.active)
        .join(active_counts, Courier.id == active_counts.c.courier_id)
        .where(
            Courier.status.in_(("assigned", "delivering")),
            active_counts.c.active < config.max_trips_per_courier,
        )
    )
    best: tuple[Courier, int] | None = None
    for courier, _active in session.execute(stmt).all():
        last_stop = _last_planned_stop(session, courier.id, redis_client)
        if last_stop is None:
            continue
        detour = chebyshev(last_stop[0], last_stop[1], pickup_x, pickup_y)
        if detour > config.batch_max_detour_cells:
            continue
        if best is None or detour < best[1]:
            best = (courier, detour)
    return best


def _last_planned_stop(
    session: Session, courier_id: object, redis_client: "Redis"
) -> tuple[int, int] | None:
    """Where this courier is headed *next* — its most recently assigned
    active trip's dropoff, or its last reported live position if it has no
    active trip (shouldn't happen for a batching candidate, but a courier
    whose position was never reported yet has none either)."""
    latest_trip = session.execute(
        select(Trip)
        .where(Trip.courier_id == courier_id, Trip.status.in_(_ACTIVE_TRIP_STATUSES))
        .order_by(Trip.assigned_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest_trip is not None:
        return (latest_trip.dropoff_x, latest_trip.dropoff_y)
    return get_position(redis_client, str(courier_id))


def attempt_assignment(
    session: Session,
    redis_client: "Redis",
    *,
    order_id: object,
    code: str,
    dropoff_x: int,
    dropoff_y: int,
    line1: str,
    config: DispatchConfig,
    speed: int,
) -> Assignment | None:
    """Try once to match `order_id` to a courier. Returns `None` if none is
    available right now — the caller (`dispatch.tasks`) reschedules a retry;
    this function never blocks or queues anything itself.

    `speed` is the live `SPEED` override — every duration below is a domain
    (real-world-minutes) figure until it's divided by `speed` right here, at
    the point of use (SPEC.md §5); nothing scaled is ever stored.
    """
    pickup_x, pickup_y = config.restaurant.x, config.restaurant.y
    now = datetime.now(UTC)

    dropoff_leg_cells = chebyshev(pickup_x, pickup_y, dropoff_x, dropoff_y)

    idle_ids = {
        str(row)
        for row in session.execute(select(Courier.id).where(Courier.status == "idle")).scalars()
    }
    nearby = nearest_within_radius(redis_client, pickup_x, pickup_y, config.search_radius_cells)
    idle_candidate = next((c for c in nearby if c.courier_id in idle_ids), None)

    if idle_candidate is not None:
        found_courier = session.get(Courier, idle_candidate.courier_id)
        assert found_courier is not None
        courier = found_courier
        from_x, from_y = idle_candidate.x, idle_candidate.y
        pickup_leg_cells = idle_candidate.distance_cells
    else:
        batch = _batch_candidate(session, redis_client, pickup_x, pickup_y, config)
        if batch is None:
            return None
        courier, detour_cells = batch
        from_x, from_y = _last_planned_stop(session, courier.id, redis_client) or (
            pickup_x,
            pickup_y,
        )
        pickup_leg_cells = detour_cells

    distance_cells = pickup_leg_cells + dropoff_leg_cells
    eta_seconds = distance_cells / _speed_cells_per_second(courier) / speed
    eta_at = now + timedelta(seconds=eta_seconds)

    trip = Trip(
        courier_id=courier.id,
        order_id=order_id,
        code=code,
        status="assigned",
        pickup_x=pickup_x,
        pickup_y=pickup_y,
        dropoff_x=dropoff_x,
        dropoff_y=dropoff_y,
        assigned_at=now,
        eta_at=eta_at,
        distance_cells=distance_cells,
    )
    session.add(trip)
    if courier.status == "idle":
        courier.status = "assigned"
    session.flush()

    grant_expires_at = now + timedelta(seconds=config.address_grant_ttl_seconds / speed)
    session.add(
        AddressGrant(
            trip_id=trip.id,
            courier_id=courier.id,
            dropoff_x=dropoff_x,
            dropoff_y=dropoff_y,
            line1=line1,
            granted_at=now,
            expires_at=grant_expires_at,
        )
    )
    session.flush()

    return Assignment(
        trip_id=trip.id,
        courier_id=courier.id,
        eta_at=eta_at,
        distance_cells=distance_cells,
        from_x=from_x,
        from_y=from_y,
        pickup_leg_cells=pickup_leg_cells,
        dropoff_leg_cells=dropoff_leg_cells,
        speed_cells_per_min=float(courier.speed_cells_per_min),
    )
