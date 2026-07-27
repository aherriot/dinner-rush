import pytest
from rest_framework.test import APIClient

from gateway.catalog.models import MenuItem
from gateway.customers.models import Address, Customer
from gateway.orders import kitchen_client
from gateway.orders import views as orders_views
from gateway.orders.models import Order
from tests.orders.conftest import customer_token, manager_token


@pytest.fixture(autouse=True)
def accepting_kitchen(monkeypatch: pytest.MonkeyPatch) -> None:
    """API tests don't run kitchen — stand in with a quote that always says
    yes, matching Phase 2/3's "capacity is unreachable" behaviour, now
    explicit rather than implicit."""
    monkeypatch.setattr(
        orders_views.kitchen_client,
        "get_capacity_quote",
        lambda items: kitchen_client.CapacityQuote(
            can_accept=True, queue_depth=0, projected_wait_s=300.0
        ),
    )


@pytest.mark.django_db
def test_accepted_order_computes_pricing_and_returns_201(
    as_customer: APIClient, menu_item: MenuItem, customer_with_address: tuple[Customer, Address]
) -> None:
    _, address = customer_with_address
    response = as_customer.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 2}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-1",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "accepted"
    assert body["subtotal_cents"] == 2400
    assert body["delivery_fee_cents"] == 299
    assert body["total_cents"] == 2699
    assert body["promised_at"] is not None


@pytest.mark.django_db
def test_missing_idempotency_key_is_a_400(
    as_customer: APIClient, menu_item: MenuItem, customer_with_address: tuple[Customer, Address]
) -> None:
    _, address = customer_with_address
    response = as_customer.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 1}]},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_redelivering_the_same_idempotency_key_is_a_no_op(
    as_customer: APIClient, menu_item: MenuItem, customer_with_address: tuple[Customer, Address]
) -> None:
    _, address = customer_with_address
    payload = {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 1}]}

    first = as_customer.post(
        "/api/v1/orders", payload, format="json", HTTP_IDEMPOTENCY_KEY="dup-1"
    )
    second = as_customer.post(
        "/api/v1/orders", payload, format="json", HTTP_IDEMPOTENCY_KEY="dup-1"
    )

    assert first.json()["code"] == second.json()["code"]
    assert Order.objects.filter(idempotency_key="dup-1").count() == 1


@pytest.mark.django_db
def test_order_for_unavailable_item_is_rejected_with_202(
    as_customer: APIClient, menu_item: MenuItem, customer_with_address: tuple[Customer, Address]
) -> None:
    menu_item.available = False
    menu_item.save()
    _, address = customer_with_address

    response = as_customer.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 1}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-unavailable",
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "item_unavailable"


@pytest.mark.django_db
def test_order_outside_delivery_range_is_rejected_with_202(
    as_customer: APIClient, menu_item: MenuItem, customer_with_address: tuple[Customer, Address]
) -> None:
    _, address = customer_with_address
    address.grid_x = 0
    address.grid_y = 0
    address.save()

    response = as_customer.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 1}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-outside",
    )

    assert response.status_code == 202
    assert response.json()["rejection_reason"] == "outside_range"


@pytest.mark.django_db
def test_order_rejected_at_capacity_when_kitchen_says_no(
    monkeypatch: pytest.MonkeyPatch,
    as_customer: APIClient,
    menu_item: MenuItem,
    customer_with_address: tuple[Customer, Address],
) -> None:
    monkeypatch.setattr(
        orders_views.kitchen_client,
        "get_capacity_quote",
        lambda items: kitchen_client.CapacityQuote(
            can_accept=False, queue_depth=41, projected_wait_s=3000.0
        ),
    )
    _, address = customer_with_address

    response = as_customer.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 1}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-at-capacity",
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "at_capacity"


@pytest.mark.django_db
def test_unavailable_item_short_circuits_before_calling_kitchen(
    monkeypatch: pytest.MonkeyPatch,
    as_customer: APIClient,
    menu_item: MenuItem,
    customer_with_address: tuple[Customer, Address],
) -> None:
    """No reason to ask kitchen about capacity for an order that's already
    rejected for a free, local reason."""
    menu_item.available = False
    menu_item.save()
    _, address = customer_with_address

    def _fail_if_called(items: list[dict[str, object]]) -> kitchen_client.CapacityQuote:
        raise AssertionError("kitchen should not have been called")

    monkeypatch.setattr(orders_views.kitchen_client, "get_capacity_quote", _fail_if_called)

    response = as_customer.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 1}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-short-circuit",
    )

    assert response.status_code == 202
    assert response.json()["rejection_reason"] == "item_unavailable"


@pytest.mark.django_db
def test_unknown_sku_is_a_validation_error_not_a_rejection(
    as_customer: APIClient, customer_with_address: tuple[Customer, Address]
) -> None:
    _, address = customer_with_address

    response = as_customer.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": "NOPE", "qty": 1}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-unknown",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_customer_cannot_order_to_another_customers_address(
    as_customer: APIClient, menu_item: MenuItem
) -> None:
    other_customer = Customer.objects.create(name="Grace Hopper", email="grace@example.com")
    other_address = Address.objects.create(
        customer=other_customer, label="Home", line1="9 Compiler Ct", grid_x=50, grid_y=50
    )

    response = as_customer.post(
        "/api/v1/orders",
        {"address_id": str(other_address.id), "items": [{"sku": menu_item.sku, "qty": 1}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-other-address",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_manager_cannot_place_orders(
    api_client: APIClient, menu_item: MenuItem, customer_with_address: tuple[Customer, Address]
) -> None:
    _, address = customer_with_address
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {manager_token()}")

    response = api_client.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 1}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-manager",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_customer_cannot_read_another_customers_order(
    api_client: APIClient, menu_item: MenuItem, customer_with_address: tuple[Customer, Address]
) -> None:
    customer, address = customer_with_address
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {customer_token(customer.id)}")
    created = api_client.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 1}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-owner",
    )
    code = created.json()["code"]

    other_customer = Customer.objects.create(name="Grace Hopper", email="grace@example.com")
    other_client = APIClient()
    other_client.credentials(HTTP_AUTHORIZATION=f"Bearer {customer_token(other_customer.id)}")

    response = other_client.get(f"/api/v1/orders/{code}")

    assert response.status_code == 403


@pytest.mark.django_db
def test_manager_can_read_any_order(
    as_customer: APIClient,
    as_manager: APIClient,
    menu_item: MenuItem,
    customer_with_address: tuple[Customer, Address],
) -> None:
    _, address = customer_with_address
    created = as_customer.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 1}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-manager-read",
    )
    code = created.json()["code"]

    response = as_manager.get(f"/api/v1/orders/{code}")

    assert response.status_code == 200


@pytest.mark.django_db
def test_timeline_is_ordered_from_place_to_current_status(
    as_customer: APIClient, menu_item: MenuItem, customer_with_address: tuple[Customer, Address]
) -> None:
    _, address = customer_with_address
    created = as_customer.post(
        "/api/v1/orders",
        {"address_id": str(address.id), "items": [{"sku": menu_item.sku, "qty": 1}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="key-timeline",
    )
    code = created.json()["code"]

    response = as_customer.get(f"/api/v1/orders/{code}/timeline")

    assert response.status_code == 200
    events = response.json()
    assert [e["event"] for e in events] == ["place", "accept"]
    assert events[0]["from_status"] is None
    assert events[1]["from_status"] == "placed"


@pytest.mark.django_db
def test_admin_speed_endpoint_rejects_non_manager(as_customer: APIClient) -> None:
    response = as_customer.post("/api/v1/admin/speed", {"speed": 10}, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_speed_endpoint_accepts_manager(as_manager: APIClient) -> None:
    response = as_manager.post("/api/v1/admin/speed", {"speed": 10}, format="json")

    assert response.status_code == 200
    assert response.json() == {"speed": 10}
