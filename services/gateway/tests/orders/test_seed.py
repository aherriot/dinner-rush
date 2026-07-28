import pytest
from django.core.management import call_command

from dinner_rush_core.config import load_config
from gateway.customers.models import Address, Customer
from gateway.orders.management.commands.seed import SIMULATOR_EMAIL_FORMAT


@pytest.mark.django_db
def test_seed_creates_exactly_population_simulator_customers() -> None:
    call_command("seed")

    population = load_config().simulator.customers.population
    assert Customer.objects.filter(email__startswith="sim").count() == population
    assert Customer.objects.filter(email=SIMULATOR_EMAIL_FORMAT.format(n=1)).exists()
    assert Customer.objects.filter(email=SIMULATOR_EMAIL_FORMAT.format(n=population)).exists()


@pytest.mark.django_db
def test_seed_is_idempotent_for_simulator_customers() -> None:
    call_command("seed")
    call_command("seed")

    population = load_config().simulator.customers.population
    assert Customer.objects.filter(email__startswith="sim").count() == population


@pytest.mark.django_db
def test_seed_gives_every_simulator_customer_exactly_one_address() -> None:
    call_command("seed")

    customer = Customer.objects.get(email=SIMULATOR_EMAIL_FORMAT.format(n=1))
    assert Address.objects.filter(customer=customer).count() == 1


@pytest.mark.django_db
def test_reseeding_does_not_move_a_simulator_customers_address() -> None:
    call_command("seed")
    first = Address.objects.get(customer__email=SIMULATOR_EMAIL_FORMAT.format(n=7))
    first_coords = (first.grid_x, first.grid_y)

    call_command("seed")
    second = Address.objects.get(customer__email=SIMULATOR_EMAIL_FORMAT.format(n=7))

    assert (second.grid_x, second.grid_y) == first_coords
