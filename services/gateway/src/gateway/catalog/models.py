from django.db import models

from gateway.common.models import UUID7Model


class MenuItem(UUID7Model):
    STATION_CHOICES = [("prep", "prep"), ("assembly", "assembly")]

    sku = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    base_price_cents = models.PositiveIntegerField()
    prep_seconds = models.PositiveIntegerField()
    bake_seconds = models.PositiveIntegerField()
    oven_slots = models.SmallIntegerField(default=1)
    station = models.CharField(max_length=10, choices=STATION_CHOICES, default="prep")
    available = models.BooleanField(default=True)
    sort_order = models.SmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return f"{self.sku} — {self.name}"
