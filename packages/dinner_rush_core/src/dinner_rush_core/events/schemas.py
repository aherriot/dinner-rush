"""Payload schemas for the event catalogue (SPEC.md §4).

Additive-only within a major version — every payload ignores unknown fields
so an old consumer doesn't choke on a new field, and a breaking change is a
new event type (`order.ready.v2`), not a mutation of this one. See
DECISIONS.md §0004 "Versioning policy".

Kitchen and dispatch don't exist yet (they're Phase 4 and 7 extractions), so
until then the gateway monolith produces every event in this file itself,
including the ones the catalogue eventually attributes to those services.
Fields that depend on infrastructure that doesn't exist yet (`oven_id`,
`courier_id`, `queue_depth`, `position`) carry honest placeholder values —
the event *shape* is real and stable; only the *producer* changes at
extraction time.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class ItemLine(_Payload):
    sku: str
    qty: int


class OrderPlacedPayload(_Payload):
    code: str
    customer_id: str
    items: list[ItemLine]
    total_cents: int
    grid_x: int
    grid_y: int


class OrderAcceptedPayload(_Payload):
    code: str
    promised_at: datetime
    items: list[ItemLine]


class OrderRejectedPayload(_Payload):
    code: str
    reason: str
    queue_depth: int


class OrderQueuedPayload(_Payload):
    code: str
    position: int
    projected_start_at: datetime


class OrderBakingPayload(_Payload):
    code: str
    oven_id: str
    slot_index: int
    frees_at: datetime


class OrderBakedPayload(_Payload):
    code: str
    actual_bake_s: float


class OrderReadyPayload(_Payload):
    code: str
    grid_x: int
    grid_y: int
    ready_at: datetime


class OrderDeliveredPayload(_Payload):
    code: str
    courier_id: str
    total_elapsed_s: float


class OrderFailedPayload(_Payload):
    code: str
    reason: str
