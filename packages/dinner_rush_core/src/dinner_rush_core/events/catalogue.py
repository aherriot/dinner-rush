"""The event catalogue: event type -> (version, payload schema, stream).

One stream per aggregate type (DECISIONS.md §0003), not per event type — the
only ordering guarantee needed is per-aggregate (`order.baked` before
`order.ready` for the same order), and cross-aggregate ordering is neither
needed nor promised.
"""

from pydantic import BaseModel, ConfigDict

from dinner_rush_core.events.schemas import (
    CourierAssignedPayload,
    CourierStatusPayload,
    ItemStartedPayload,
    OrderAcceptedPayload,
    OrderBakedPayload,
    OrderBakingPayload,
    OrderDeliveredPayload,
    OrderDeliveringPayload,
    OrderFailedPayload,
    OrderPickedUpPayload,
    OrderPlacedPayload,
    OrderQueuedPayload,
    OrderReadyPayload,
    OrderRejectedPayload,
    OrderUnassignedPayload,
    OvenSlotFreedPayload,
    OvenStatusChangedPayload,
    StationDownPayload,
)


class EventSchema(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    version: int
    payload_model: type[BaseModel]
    stream: str


EVENT_CATALOGUE: dict[str, EventSchema] = {
    "order.placed": EventSchema(version=1, payload_model=OrderPlacedPayload, stream="events:order"),
    "order.accepted": EventSchema(
        version=1, payload_model=OrderAcceptedPayload, stream="events:order"
    ),
    "order.rejected": EventSchema(
        version=1, payload_model=OrderRejectedPayload, stream="events:order"
    ),
    "order.queued": EventSchema(version=1, payload_model=OrderQueuedPayload, stream="events:order"),
    "order.baking": EventSchema(version=1, payload_model=OrderBakingPayload, stream="events:order"),
    "order.baked": EventSchema(version=1, payload_model=OrderBakedPayload, stream="events:order"),
    "order.ready": EventSchema(version=1, payload_model=OrderReadyPayload, stream="events:order"),
    "order.picked_up": EventSchema(
        version=1, payload_model=OrderPickedUpPayload, stream="events:order"
    ),
    "order.delivering": EventSchema(
        version=1, payload_model=OrderDeliveringPayload, stream="events:order"
    ),
    "order.delivered": EventSchema(
        version=1, payload_model=OrderDeliveredPayload, stream="events:order"
    ),
    "order.failed": EventSchema(version=1, payload_model=OrderFailedPayload, stream="events:order"),
    "order.unassigned": EventSchema(
        version=1, payload_model=OrderUnassignedPayload, stream="events:order"
    ),
    "item.started": EventSchema(version=1, payload_model=ItemStartedPayload, stream="events:order"),
    "courier.online": EventSchema(
        version=1, payload_model=CourierStatusPayload, stream="events:courier"
    ),
    "courier.offline": EventSchema(
        version=1, payload_model=CourierStatusPayload, stream="events:courier"
    ),
    "courier.assigned": EventSchema(
        version=1, payload_model=CourierAssignedPayload, stream="events:courier"
    ),
    # `oven`/`station` have no dedicated stream in DECISIONS.md §0003's fixed
    # three (`events:order`, `events:oven`, `events:courier`) — both kitchen-
    # infra event types share `events:oven`.
    "oven.slot_freed": EventSchema(
        version=1, payload_model=OvenSlotFreedPayload, stream="events:oven"
    ),
    "oven.down": EventSchema(
        version=1, payload_model=OvenStatusChangedPayload, stream="events:oven"
    ),
    "oven.restored": EventSchema(
        version=1, payload_model=OvenStatusChangedPayload, stream="events:oven"
    ),
    "station.down": EventSchema(version=1, payload_model=StationDownPayload, stream="events:oven"),
}


class UnknownEventTypeError(KeyError):
    pass


def stream_for(event_type: str) -> str:
    try:
        return EVENT_CATALOGUE[event_type].stream
    except KeyError as exc:
        raise UnknownEventTypeError(event_type) from exc


def validate_payload(event_type: str, payload: dict[str, object]) -> BaseModel:
    try:
        schema = EVENT_CATALOGUE[event_type]
    except KeyError as exc:
        raise UnknownEventTypeError(event_type) from exc
    return schema.payload_model.model_validate(payload)
