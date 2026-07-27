"""The event spine's own tables (DECISIONS.md §0004).

`Outbox` and `ProcessedEvent` are framework-glue only — the logic that reads
and writes them lives in `dinner_rush_core.outbox`, which takes a plain
cursor rather than these models, so it works unmodified once kitchen and
dispatch grow their own copies of this same shape in Phase 4/7.

`EventTypeCounter` is the "analytics" consumer's side effect from SPEC.md
§4's classification table — a Postgres write that must be effectively-once,
made concrete enough to write a redelivery-is-a-no-op test against.
"""

from django.db import models


class Outbox(models.Model):
    id = models.BigAutoField(primary_key=True)
    event_id = models.UUIDField(unique=True)
    stream = models.CharField(max_length=100)
    envelope = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "outbox"  # matches the table name dinner_rush_core.outbox expects by default
        indexes = [
            models.Index(
                fields=["id"],
                name="outbox_unpublished",
                condition=models.Q(published_at__isnull=True),
            ),
        ]


class ProcessedEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    consumer_group = models.CharField(max_length=100)
    event_id = models.UUIDField()
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "processed_event"
        constraints = [
            models.UniqueConstraint(
                fields=["consumer_group", "event_id"], name="processed_event_dedup"
            ),
        ]


class EventTypeCounter(models.Model):
    event_type = models.CharField(max_length=100, unique=True)
    count = models.BigIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.event_type}: {self.count}"
