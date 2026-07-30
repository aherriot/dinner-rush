import uuid
from datetime import UTC, datetime

import pytest

from dinner_rush_core.events.envelope import EventEnvelope
from front_of_house.customers.models import Address, Customer
from front_of_house.eventing.handlers import handle_order_sync
from front_of_house.eventing.models import ProcessedEvent
from front_of_house.orders.models import Order


def _order_event(
    order_id: uuid.UUID, event_type: str, sequence: int = 3, producer: str = "kitchen@0.1.0"
) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid.uuid4(),
        event_type=event_type,
        event_version=1,
        occurred_at=datetime.now(UTC),
        aggregate_type="order",
        aggregate_id=order_id,
        sequence=sequence,
        correlation_id=order_id,
        producer=producer,
        payload={"code": "4400"},
    )


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
def test_the_full_kitchen_chain_advances_the_order_to_ready(
    customer_with_address: tuple[Customer, Address],
) -> None:
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


@pytest.mark.django_db
def test_the_full_dispatch_chain_advances_a_ready_order_to_delivered(
    customer_with_address: tuple[Customer, Address],
) -> None:
    """Dispatch now drives `ready -> assigned -> picked_up -> delivering ->
    delivered` for real (Phase 7) — front-of-house just folds each event in, same
    as it already does for kitchen's chain."""
    customer, address = customer_with_address
    order = Order.objects.create(
        code="4405",
        customer=customer,
        address=address,
        status="ready",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
    )

    handle_order_sync(_order_event(order.id, "courier.assigned", producer="dispatch@0.1.0"))
    order.refresh_from_db()
    assert order.status == "assigned"

    for event_type in ("order.picked_up", "order.delivering", "order.delivered"):
        handle_order_sync(_order_event(order.id, event_type, producer="dispatch@0.1.0"))

    order.refresh_from_db()
    assert order.status == "delivered"
    assert order.delivered_at is not None
    assert list(order.timeline.values_list("event", flat=True)) == [
        "assign",
        "pick_up",
        "depart",
        "deliver",
    ]


@pytest.mark.django_db
def test_order_unassigned_returns_the_order_to_ready(
    customer_with_address: tuple[Customer, Address],
) -> None:
    """The courier-offline chaos scenario (ADR 0007 §4): the order goes back
    to `ready` so dispatch's own reassignment attempt has something to
    assign again."""
    customer, address = customer_with_address
    order = Order.objects.create(
        code="4406",
        customer=customer,
        address=address,
        status="assigned",
        subtotal_cents=1200,
        delivery_fee_cents=299,
        total_cents=1499,
    )

    handle_order_sync(_order_event(order.id, "order.unassigned", producer="dispatch@0.1.0"))

    order.refresh_from_db()
    assert order.status == "ready"
    assert list(order.timeline.values_list("event", flat=True)) == ["unassign"]


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
