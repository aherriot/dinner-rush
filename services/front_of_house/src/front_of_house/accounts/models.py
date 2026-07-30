from django.conf import settings
from django.db import models

from front_of_house.common.models import UUID7Model


class Staff(UUID7Model):
    ROLE_CHOICES = [("kitchen", "kitchen"), ("manager", "manager")]

    name = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return f"{self.name} ({self.role})"
