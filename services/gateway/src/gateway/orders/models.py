from django.db import models

from gateway.catalog.models import MenuItem
from gateway.common.models import UUID7Model
from gateway.customers.models import Address, Customer
from gateway.orders.fsm import ALL_STATUSES

STATUS_CHOICES = [(status, status) for status in sorted(ALL_STATUSES)]
REJECTION_REASONS = [
    ("at_capacity", "at_capacity"),
    ("item_unavailable", "item_unavailable"),
    ("outside_range", "outside_range"),
]


class OrderCodeSequence(models.Model):
    """A row per order code issued. Postgres's real auto-increment sequence
    is the allocator — no locking needed, unlike the oven-slot contention
    problem Phase 4 solves for real."""


class Order(UUID7Model):
    code = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="placed")

    subtotal_cents = models.PositiveIntegerField()
    delivery_fee_cents = models.PositiveIntegerField()
    total_cents = models.PositiveIntegerField()

    placed_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    promised_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    rejection_reason = models.CharField(
        max_length=20, choices=REJECTION_REASONS, null=True, blank=True
    )
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-placed_at"]

    def __str__(self) -> str:
        return self.code


class OrderItem(UUID7Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name="+")
    qty = models.PositiveSmallIntegerField()
    unit_price_cents = models.PositiveIntegerField()

    # Snapshotted at order time — an order's history must not change when the
    # menu does (SPEC.md §1.1).
    name_snapshot = models.CharField(max_length=100)
    prep_seconds_snapshot = models.PositiveIntegerField()
    bake_seconds_snapshot = models.PositiveIntegerField()

    def __str__(self) -> str:
        return f"{self.qty}x {self.name_snapshot}"


class OrderStatusEvent(UUID7Model):
    """Append-only status history — the Phase 2 stand-in for the outbox.

    Phase 3 replaces this with the real event envelope + Redis Streams; until
    then this is what `GET /orders/{code}/timeline` reads.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="timeline")
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20)
    event = models.CharField(max_length=20)
    occurred_at = models.DateTimeField(auto_now_add=True)

    # Set only on the `reject` event — mirrors the `order.rejected` outbox
    # payload so the reason lives with the event that caused it, not just
    # denormalized onto the terminal Order row.
    reason = models.CharField(max_length=20, choices=REJECTION_REASONS, null=True, blank=True)
    queue_depth = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["occurred_at"]

    def __str__(self) -> str:
        return f"{self.order.code}: {self.from_status} -> {self.to_status}"
