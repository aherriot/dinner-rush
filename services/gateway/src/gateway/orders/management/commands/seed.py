"""`make seed` — menu, demo customers/addresses, manager + kitchen staff.

Idempotent: safe to run against an already-seeded database (upserts by the
natural key — `sku`, `email`, `username`).
"""

from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from dinner_rush_core.config import load_config
from gateway.accounts.models import Staff
from gateway.catalog.models import MenuItem
from gateway.customers.models import Address, Customer

DEMO_CUSTOMERS = [
    # name, email, phone, address label, line1, grid_x, grid_y
    ("Ada Lovelace", "ada@example.com", "555-0100", "Home", "12 Analytical Ave", 55, 48),
    ("Grace Hopper", "grace@example.com", "555-0101", "Home", "9 Compiler Ct", 40, 60),
    ("Alan Turing", "alan@example.com", "555-0102", "Office", "1 Enigma Way", 95, 95),
]


class Command(BaseCommand):
    help = "Seed the menu, demo customers/addresses, and manager/kitchen staff logins."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        config = load_config()

        for item in config.menu:
            MenuItem.objects.update_or_create(
                sku=item.sku,
                defaults={
                    "name": item.name,
                    "base_price_cents": item.price_cents,
                    "prep_seconds": item.prep_seconds,
                    "bake_seconds": item.bake_seconds,
                    "oven_slots": item.oven_slots,
                },
            )
        self.stdout.write(f"seeded {len(config.menu)} menu items")

        for name, email, phone, label, line1, grid_x, grid_y in DEMO_CUSTOMERS:
            customer, _ = Customer.objects.update_or_create(
                email=email, defaults={"name": name, "phone": phone}
            )
            Address.objects.update_or_create(
                customer=customer,
                label=label,
                defaults={"line1": line1, "grid_x": grid_x, "grid_y": grid_y},
            )
        self.stdout.write(f"seeded {len(DEMO_CUSTOMERS)} demo customers")

        self._seed_staff(username="manager", name="Morgan Manager", role="manager")
        self._seed_staff(username="kitchen", name="Kai Kitchen", role="kitchen")
        self.stdout.write(
            self.style.SUCCESS("seed complete — staff logins: manager/manager, kitchen/kitchen")
        )

    def _seed_staff(self, *, username: str, name: str, role: str) -> None:
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        if created:
            user.set_password(username)  # demo-only credentials, see ADR 0002
            user.save()
        Staff.objects.update_or_create(user=user, defaults={"name": name, "role": role})
