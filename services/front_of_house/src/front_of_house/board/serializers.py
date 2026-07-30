from typing import Any

from rest_framework import serializers

from front_of_house.orders.serializers import OrderSerializer


class KitchenSnapshotSerializer(serializers.Serializer[Any]):
    """Passthrough — kitchen's own `TicketOut`/`OvenOut` (FastAPI/Pydantic)
    are already the wire shape the board wants; front-of-house doesn't re-model
    them. `None` means kitchen didn't answer (`kitchen_client.get_queue`/
    `get_ovens`'s degrade-not-fail contract), not an empty result."""

    queue = serializers.JSONField(allow_null=True)
    ovens = serializers.JSONField(allow_null=True)


class DispatchSnapshotSerializer(serializers.Serializer[Any]):
    """Passthrough — same reasoning as `KitchenSnapshotSerializer`, for
    dispatch's `TripOut`/`CourierOut`/`BacklogOut`."""

    trips = serializers.JSONField(allow_null=True)
    couriers = serializers.JSONField(allow_null=True)
    #: `None` means dispatch didn't answer (`dispatch_client.get_backlog`'s
    #: degrade-not-fail contract) — distinct from an empty backlog, which is
    #: `{"ready_count": 0, "oldest_waiting_seconds": null}`.
    backlog = serializers.JSONField(allow_null=True)


class BoardSnapshotSerializer(serializers.Serializer[Any]):
    """`GET /board/snapshot` (SPEC.md §3.1) — the board's cold-load state."""

    orders = OrderSerializer(many=True)
    kitchen = KitchenSnapshotSerializer()
    dispatch = DispatchSnapshotSerializer()


class OvenStatusSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=["available", "down"])


class ScenarioToggleSerializer(serializers.Serializer[Any]):
    scenario = serializers.CharField()
    active = serializers.BooleanField()
    overrides = serializers.JSONField()
    actions_applied = serializers.JSONField()


class ScenariosActiveSerializer(serializers.Serializer[Any]):
    overrides = serializers.JSONField()
    scenarios = serializers.ListField(child=serializers.CharField())
