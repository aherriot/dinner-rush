from django.db import models

from dinner_rush_core.ids import uuid7


class UUID7Model(models.Model):
    """Base for every gateway entity — UUIDv7 primary key per SPEC.md §1."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    class Meta:
        abstract = True
