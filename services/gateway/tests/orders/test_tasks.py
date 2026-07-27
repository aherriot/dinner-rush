import pytest

from gateway.customers.models import Address, Customer
from gateway.eventing.models import Outbox
from gateway.orders.models import Order, OrderItem
from gateway.orders.tasks import STEPS, advance_order


@pytest.mark.django_db
def test_advance_order_walks_an_accepted_order_all_the_way_to_delivered(
    monkeypatch: pytest.MonkeyPatch,
    customer_with_address: tuple[Customer, Address],
    menu_item: object,
) -> None:
    # Each step's own chaining to the next is exercised by the view-level
    # integration test; here each step is driven explicitly so the test
    # doesn't depend on a live Celery broker/worker actually running.
    monkeypatch.setattr(advance_order, "apply_async", lambda *a, **kw: None)

    customer, address = customer_with_address
    order = Order.objects.create(
        code="9000",
        customer=customer,
        address=address,
        status="accepted",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
    )
    OrderItem.objects.create(
        order=order,
        menu_item=menu_item,
        qty=1,
        unit_price_cents=1200,
        name_snapshot="Margherita",
        prep_seconds_snapshot=90,
        bake_seconds_snapshot=420,
    )

    causation_id = None
    for step_index in range(len(STEPS)):
        advance_order(
            str(order.id), step_index, sequence=10 + step_index, causation_id=causation_id
        )
        outbox_rows = list(Outbox.objects.order_by("id"))
        if outbox_rows:
            causation_id = str(outbox_rows[-1].event_id)

    order.refresh_from_db()
    assert order.status == "delivered"
    assert order.delivered_at is not None

    fired_events = list(order.timeline.values_list("event", flat=True))
    assert fired_events == [step.event for step in STEPS]

    published_event_types = list(
        Outbox.objects.order_by("id").values_list("envelope__event_type", flat=True)
    )
    assert published_event_types == [
        "order.queued",
        "order.baking",
        "order.baked",
        "order.ready",
        "order.delivered",
    ]


@pytest.mark.django_db
def test_advance_order_stops_early_if_the_order_is_already_terminal(
    customer_with_address: tuple[Customer, Address],
) -> None:
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

    advance_order(str(order.id), 0, sequence=1, causation_id=None)

    order.refresh_from_db()
    assert order.status == "rejected"
    assert order.timeline.count() == 0
    assert Outbox.objects.count() == 0
