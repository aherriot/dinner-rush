from django.db import models

from front_of_house.common.models import UUID7Model


class Customer(UUID7Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Address(UUID7Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=50, blank=True, default="")
    line1 = models.CharField(max_length=200)
    grid_x = models.SmallIntegerField()
    grid_y = models.SmallIntegerField()
    notes = models.CharField(max_length=200, blank=True, default="")

    def __str__(self) -> str:
        return f"{self.label or self.line1} ({self.grid_x},{self.grid_y})"
