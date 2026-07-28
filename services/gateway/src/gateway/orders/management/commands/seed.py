"""`make seed` — menu, demo customers/addresses, manager + kitchen staff, and
the simulator's customer population.

Idempotent: safe to run against an already-seeded database (upserts by the
natural key — `sku`, `email`, `username`).
"""

import random
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

#: `sim{n:04d}@example.com` — the simulator (Phase 6) derives the exact same
#: emails from `config.yaml`'s `simulator.customers.population` and never
#: creates its own customers (no signup flow, ADR 0002 §2), so the two sides
#: must agree on the pattern without talking to each other.
SIMULATOR_EMAIL_FORMAT = "sim{n:04d}@example.com"


class Command(BaseCommand):
    help = (
        "Seed the menu, demo customers/addresses, the simulator's customer "
        "population, and manager/kitchen staff logins."
    )

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

        population = config.simulator.customers.population
        self._seed_simulator_population(
            population,
            restaurant_x=config.dispatch.restaurant.x,
            restaurant_y=config.dispatch.restaurant.y,
            max_distance=config.gateway.max_delivery_distance_cells,
        )
        self.stdout.write(f"seeded {population} simulator customers")

        self._seed_staff(username="manager", name="Morgan Manager", role="manager")
        self._seed_staff(username="kitchen", name="Kai Kitchen", role="kitchen")
        self.stdout.write(
            self.style.SUCCESS("seed complete — staff logins: manager/manager, kitchen/kitchen")
        )

    def _seed_simulator_population(
        self, population: int, *, restaurant_x: int, restaurant_y: int, max_distance: int
    ) -> None:
        """One customer + one address per `n` in `1..population`, matching
        `SIMULATOR_EMAIL_FORMAT` exactly. Addresses are placed within
        `max_distance` of the restaurant nine times out of ten — mostly
        orderable, with enough of a tail beyond range that `outside_range`
        rejections are a real, occasionally-observed outcome rather than
        something the simulator has to force.

        Each customer's address is derived from a `random.Random(n)` seeded
        on its own index, not the shared `random` module — reseeding on every
        idempotent re-run must reproduce the exact same address, independent
        of how many other calls to `random` happened first this process.
        """
        for n in range(1, population + 1):
            rng = random.Random(n)
            in_range = rng.random() < 0.9
            radius = max_distance if in_range else max_distance + rng.randint(5, 20)
            grid_x = restaurant_x + rng.randint(-radius, radius)
            grid_y = restaurant_y + rng.randint(-radius, radius)

            email = SIMULATOR_EMAIL_FORMAT.format(n=n)
            customer, _ = Customer.objects.update_or_create(
                email=email, defaults={"name": f"Sim Customer {n:04d}", "phone": ""}
            )
            Address.objects.update_or_create(
                customer=customer,
                label="Home",
                defaults={"line1": f"{n} Simulated St", "grid_x": grid_x, "grid_y": grid_y},
            )

    def _seed_staff(self, *, username: str, name: str, role: str) -> None:
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        if created:
            user.set_password(username)  # demo-only credentials, see ADR 0002
            user.save()
        Staff.objects.update_or_create(user=user, defaults={"name": name, "role": role})
