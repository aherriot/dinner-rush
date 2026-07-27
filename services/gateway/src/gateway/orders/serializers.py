from typing import Any

from django.utils import timezone
from rest_framework import serializers

from gateway.orders.fsm import is_terminal
from gateway.orders.models import Order, OrderItem, OrderStatusEvent


class OrderItemRequestSerializer(serializers.Serializer[Any]):
    sku = serializers.CharField()
    qty = serializers.IntegerField(min_value=1)


class OrderCreateRequestSerializer(serializers.Serializer[Any]):
    address_id = serializers.UUIDField()
    items = OrderItemRequestSerializer(many=True)

    def validate_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not items:
            raise serializers.ValidationError("cart must contain at least one item")
        return items


class OrderItemSerializer(serializers.ModelSerializer[OrderItem]):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "menu_item",
            "qty",
            "unit_price_cents",
            "name_snapshot",
            "prep_seconds_snapshot",
            "bake_seconds_snapshot",
        ]


class OrderSerializer(serializers.ModelSerializer[Order]):
    items = OrderItemSerializer(many=True, read_only=True)
    late = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "code",
            "status",
            "subtotal_cents",
            "delivery_fee_cents",
            "total_cents",
            "placed_at",
            "accepted_at",
            "promised_at",
            "ready_at",
            "delivered_at",
            "rejection_reason",
            "items",
            "late",
        ]

    def get_late(self, obj: Order) -> bool:
        """Derived, never stored (SPEC.md §2) — now() > promised_at, not terminal."""
        if is_terminal(obj.status) or obj.promised_at is None:
            return False
        return timezone.now() > obj.promised_at


class OrderStatusEventSerializer(serializers.ModelSerializer[OrderStatusEvent]):
    class Meta:
        model = OrderStatusEvent
        fields = ["from_status", "to_status", "event", "occurred_at"]
