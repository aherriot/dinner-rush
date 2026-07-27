import uuid
from datetime import UTC, datetime

import pytest

from dinner_rush_core.events.envelope import EventEnvelope
from gateway.customers.models import Address, Customer
from gateway.eventing.handlers import handle_order_sync
from gateway.eventing.models import ProcessedEvent
from gateway.orders.models import Order
from gateway.orders.tasks import advance_order


def _order_event(order_id: uuid.UUID, event_type: str, sequence: int = 3) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid.uuid4(),
        event_type=event_type,
        event_version=1,
        occurred_at=datetime.now(UTC),
        aggregate_type="order",
        aggregate_id=order_id,
        sequence=sequence,
        correlation_id=order_id,
        producer="kitchen@0.1.0",
        payload={"code": "4400"},
    )


@pytest.fixture(autouse=True)
def _no_real_dispatch_scheduling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(advance_order, "apply_async", lambda *a, **kw: None)


@pytest.mark.django_db
def test_order_queued_advances_an_accepted_order_to_queued(
    customer_with_address: tuple[Customer, Address],
) -> None:
    customer, address = customer_with_address
    order = Order.objects.create(
        code="4400",
        customer=customer,
        address=address,
        status="accepted",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
    )

    handle_order_sync(_order_event(order.id, "order.queued"))

    order.refresh_from_db()
    assert order.status == "queued"
    assert list(order.timeline.values_list("event", flat=True)) == ["enqueue"]


@pytest.mark.django_db
def test_the_full_kitchen_chain_advances_the_order_to_ready_and_kicks_off_dispatch(
    monkeypatch: pytest.MonkeyPatch, customer_with_address: tuple[Customer, Address]
) -> None:
    scheduled = []
    monkeypatch.setattr(
        advance_order, "apply_async", lambda args, countdown: scheduled.append(args)
    )

    customer, address = customer_with_address
    order = Order.objects.create(
        code="4401",
        customer=customer,
        address=address,
        status="accepted",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
    )

    for event_type in ("order.queued", "order.baking", "order.baked", "order.ready"):
        handle_order_sync(_order_event(order.id, event_type))

    order.refresh_from_db()
    assert order.status == "ready"
    assert order.ready_at is not None
    assert list(order.timeline.values_list("event", flat=True)) == [
        "enqueue",
        "start_bake",
        "finish_bake",
        "mark_ready",
    ]
    assert len(scheduled) == 1  # start_dispatch_progression fired exactly once


@pytest.mark.django_db
def test_redelivering_the_same_event_is_a_no_op(
    customer_with_address: tuple[Customer, Address],
) -> None:
    customer, address = customer_with_address
    order = Order.objects.create(
        code="4402",
        customer=customer,
        address=address,
        status="accepted",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
    )
    envelope = _order_event(order.id, "order.queued")

    handle_order_sync(envelope)
    handle_order_sync(envelope)

    order.refresh_from_db()
    assert order.status == "queued"
    assert order.timeline.count() == 1
    assert ProcessedEvent.objects.filter(consumer_group="cg:order-sync").count() == 1


@pytest.mark.django_db
def test_events_with_no_fsm_mapping_are_ignored(
    customer_with_address: tuple[Customer, Address],
) -> None:
    customer, address = customer_with_address
    order = Order.objects.create(
        code="4403",
        customer=customer,
        address=address,
        status="accepted",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
    )

    handle_order_sync(_order_event(order.id, "order.placed"))

    order.refresh_from_db()
    assert order.status == "accepted"
    assert order.timeline.count() == 0


@pytest.mark.django_db
def test_a_terminal_order_is_left_alone(customer_with_address: tuple[Customer, Address]) -> None:
    customer, address = customer_with_address
    order = Order.objects.create(
        code="4404",
        customer=customer,
        address=address,
        status="delivered",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
    )

    handle_order_sync(_order_event(order.id, "order.queued"))

    order.refresh_from_db()
    assert order.status == "delivered"
    assert order.timeline.count() == 0
