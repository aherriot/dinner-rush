from typing import Any

from rest_framework import serializers

from gateway.catalog.models import MenuItem


class MenuItemSerializer(serializers.ModelSerializer[MenuItem]):
    class Meta:
        model = MenuItem
        fields = [
            "id",
            "sku",
            "name",
            "description",
            "base_price_cents",
            "prep_seconds",
            "bake_seconds",
            "oven_slots",
            "station",
            "available",
            "sort_order",
        ]


class MenuAvailabilitySerializer(serializers.Serializer[Any]):
    available = serializers.BooleanField()
