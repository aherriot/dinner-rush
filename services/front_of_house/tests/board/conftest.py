import pytest
from rest_framework.test import APIClient

from front_of_house.catalog.models import MenuItem
from front_of_house.customers.models import Address, Customer
from tests.orders.conftest import customer_token, kitchen_token, manager_token


@pytest.fixture
def menu_item(db: None) -> MenuItem:
    return MenuItem.objects.create(
        sku="MARG",
        name="Margherita",
        base_price_cents=1200,
        prep_seconds=90,
        bake_seconds=420,
        oven_slots=1,
    )


@pytest.fixture
def customer_with_address(db: None) -> tuple[Customer, Address]:
    customer = Customer.objects.create(name="Ada Lovelace", email="ada-board@example.com")
    address = Address.objects.create(
        customer=customer, label="Home", line1="12 Analytical Ave", grid_x=50, grid_y=50
    )
    return customer, address


@pytest.fixture
def as_customer(customer_with_address: tuple[Customer, Address]) -> APIClient:
    customer, _ = customer_with_address
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {customer_token(customer.id)}")
    return client


@pytest.fixture
def as_manager() -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {manager_token()}")
    return client


@pytest.fixture
def as_kitchen() -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {kitchen_token()}")
    return client
