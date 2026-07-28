"""Request/response shapes for the FastAPI surface (SPEC.md §3.3)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ItemLineIn(BaseModel):
    sku: str
    qty: int


class CapacityQuoteRequest(BaseModel):
    items: list[ItemLineIn]


class CapacityQuoteResponse(BaseModel):
    can_accept: bool
    queue_depth: int
    projected_wait_s: float


class TicketOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    code: str
    status: str
    items: list[dict[str, object]]
    total_bake_seconds: int
    queued_at: datetime
    started_at: datetime | None
    baked_at: datetime | None
    ready_at: datetime | None
    oven_slot_id: uuid.UUID | None
    priority: int

    model_config = {"from_attributes": True}


class OvenSlotOut(BaseModel):
    id: uuid.UUID
    slot_index: int
    order_id: uuid.UUID | None
    claimed_at: datetime | None
    frees_at: datetime | None

    model_config = {"from_attributes": True}


class OvenOut(BaseModel):
    id: uuid.UUID
    name: str
    slot_count: int
    status: str
    slots: list[OvenSlotOut]

    model_config = {"from_attributes": True}


class TicketAdvanceRequest(BaseModel):
    event: str


class OvenStatusUpdateRequest(BaseModel):
    status: str
