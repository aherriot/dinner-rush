"""Request/response shapes for the FastAPI surface (SPEC.md §3.4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class CourierOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    vehicle: str
    speed_cells_per_min: float
    shift_started_at: datetime | None
    #: Last-reported Redis GEO position (`dispatch.geo`) — `None` until a
    #: courier has ever reported one. Not a mapped column: assembled by the
    #: board_router at read time, same "Redis caches, Postgres decides" split
    #: as oven state in kitchen's `OvenOut`.
    x: int | None = None
    y: int | None = None

    model_config = {"from_attributes": True}


class CourierStatusRequest(BaseModel):
    status: str  # online | offline


class CourierPositionRequest(BaseModel):
    x: int
    y: int


class TripOut(BaseModel):
    id: uuid.UUID
    courier_id: uuid.UUID
    order_id: uuid.UUID
    code: str
    status: str
    pickup_x: int
    pickup_y: int
    dropoff_x: int
    dropoff_y: int
    assigned_at: datetime
    picked_up_at: datetime | None
    delivered_at: datetime | None
    failed_at: datetime | None
    eta_at: datetime
    distance_cells: int
    failure_reason: str | None

    model_config = {"from_attributes": True}


class DropoffOut(BaseModel):
    line1: str
    dropoff_x: int
    dropoff_y: int


class BacklogOut(BaseModel):
    """`GET /backlog` — orders with `pending_dropoff.ready_at` set (i.e.
    `order.ready` has actually fired) and no `trip` row yet: genuinely boxed
    and waiting on an assignment the retry loop hasn't found a courier for.
    Excludes orders still queued/prepping/baking — those have a
    `pending_dropoff` row too (cached ahead of time on `order.placed`, ADR
    0007 §1) but aren't `ready_count`'s concern. Not visible anywhere else on
    the board; this is the number that would have caught a stuck assignment
    loop immediately."""

    ready_count: int
    #: Age of the oldest such row since it went `ready` (not since
    #: `order.placed`), or `None` when the backlog is empty — never `0`, so
    #: an empty backlog can't be confused with "just started waiting".
    oldest_waiting_seconds: float | None


class TripFailRequest(BaseModel):
    reason: str
