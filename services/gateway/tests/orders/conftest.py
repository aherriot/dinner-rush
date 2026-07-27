import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from gateway.catalog.models import MenuItem
from gateway.customers.models import Address, Customer


def customer_token(customer_id: object) -> str:
    refresh = RefreshToken()
    refresh["role"] = "customer"
    refresh["customer_id"] = str(customer_id)
    return str(refresh.access_token)


def manager_token() -> str:
    refresh = RefreshToken()
    refresh["role"] = "manager"
    refresh["staff_id"] = "test-manager"
    return str(refresh.access_token)


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


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
    customer = Customer.objects.create(name="Ada Lovelace", email="ada@example.com")
    address = Address.objects.create(
        customer=customer, label="Home", line1="12 Analytical Ave", grid_x=50, grid_y=50
    )
    return customer, address


@pytest.fixture
def as_customer(customer_with_address: tuple[Customer, Address]) -> APIClient:
    # A dedicated client, not the shared `api_client` fixture — a test using
    # both `as_customer` and `as_manager` together needs two distinct clients,
    # not one client with its credentials overwritten by the second fixture.
    customer, _ = customer_with_address
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {customer_token(customer.id)}")
    return client


@pytest.fixture
def as_manager() -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {manager_token()}")
    return client
