import pytest
from django.utils import timezone

from gateway.customers.models import Address, Customer
from gateway.orders import progression
from gateway.orders.models import Order


@pytest.mark.django_db
def test_run_advances_an_accepted_order_all_the_way_to_delivered(
    monkeypatch: pytest.MonkeyPatch, customer_with_address: tuple[Customer, Address]
) -> None:
    monkeypatch.setattr(progression.time, "sleep", lambda seconds: None)
    customer, address = customer_with_address
    order = Order.objects.create(
        code="9000",
        customer=customer,
        address=address,
        status="accepted",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
        accepted_at=timezone.now(),
    )

    progression._run(str(order.id))

    order.refresh_from_db()
    assert order.status == "delivered"
    assert order.delivered_at is not None

    fired_events = list(order.timeline.values_list("event", flat=True))
    assert fired_events == [event for event, _ in progression.STEPS]


@pytest.mark.django_db
def test_run_stops_early_if_the_order_is_already_terminal(
    monkeypatch: pytest.MonkeyPatch, customer_with_address: tuple[Customer, Address]
) -> None:
    monkeypatch.setattr(progression.time, "sleep", lambda seconds: None)
    customer, address = customer_with_address
    order = Order.objects.create(
        code="9001",
        customer=customer,
        address=address,
        status="rejected",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
        rejection_reason="item_unavailable",
    )

    progression._run(str(order.id))

    order.refresh_from_db()
    assert order.status == "rejected"
    assert order.timeline.count() == 0
