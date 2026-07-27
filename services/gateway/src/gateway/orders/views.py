from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from dinner_rush_core.config import load_config
from gateway.accounts.speed import get_speed
from gateway.catalog.models import MenuItem
from gateway.common.authentication import get_actor
from gateway.common.permissions import IsCustomer, IsOwnOrderOrManager
from gateway.customers.models import Address, Customer
from gateway.eventing.writer import build_envelope, write_outbox_event
from gateway.orders import pricing, rejection
from gateway.orders.fsm import apply_transition
from gateway.orders.models import Order, OrderCodeSequence, OrderItem, OrderStatusEvent
from gateway.orders.serializers import (
    OrderCreateRequestSerializer,
    OrderSerializer,
    OrderStatusEventSerializer,
)
from gateway.orders.tasks import start_progression


def _next_order_code(order_code_start: int) -> str:
    sequence = OrderCodeSequence.objects.create()
    return str(order_code_start + sequence.id - 1)


class OrderCreateView(APIView):
    """`POST /orders` (SPEC.md §3.1). Rejection is a 202, not an error."""

    permission_classes = [IsCustomer]

    @extend_schema(
        request=OrderCreateRequestSerializer,
        responses={201: OrderSerializer, 202: OrderSerializer},
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                location=OpenApiParameter.HEADER,
                required=True,
                type=str,
            )
        ],
    )
    def post(self, request: Request) -> Response:
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            raise ValidationError("Idempotency-Key header is required")

        existing = Order.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            status_code = 202 if existing.status == "rejected" else 201
            return Response(OrderSerializer(existing).data, status=status_code)

        serializer = OrderCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        customer = get_object_or_404(Customer, id=get_actor(request).customer_id)
        address = get_object_or_404(Address, id=payload["address_id"], customer=customer)

        skus = [item["sku"] for item in payload["items"]]
        menu_items_by_sku = {mi.sku: mi for mi in MenuItem.objects.filter(sku__in=skus)}
        missing_skus = set(skus) - menu_items_by_sku.keys()
        if missing_skus:
            raise ValidationError(f"unknown menu item sku(s): {sorted(missing_skus)}")

        config = load_config()

        with transaction.atomic():
            order = Order.objects.create(
                code=_next_order_code(config.gateway.order_code_start),
                customer=customer,
                address=address,
                status="placed",
                subtotal_cents=0,
                delivery_fee_cents=0,
                total_cents=0,
                idempotency_key=idempotency_key,
            )
            OrderStatusEvent.objects.create(
                order=order, from_status=None, to_status="placed", event="place"
            )

            order_items = [
                OrderItem(
                    order=order,
                    menu_item=menu_items_by_sku[item["sku"]],
                    qty=item["qty"],
                    unit_price_cents=menu_items_by_sku[item["sku"]].base_price_cents,
                    name_snapshot=menu_items_by_sku[item["sku"]].name,
                    prep_seconds_snapshot=menu_items_by_sku[item["sku"]].prep_seconds,
                    bake_seconds_snapshot=menu_items_by_sku[item["sku"]].bake_seconds,
                )
                for item in payload["items"]
            ]
            OrderItem.objects.bulk_create(order_items)

            item_lines: list[dict[str, object]] = [
                {"sku": item["sku"], "qty": item["qty"]} for item in payload["items"]
            ]
            placed_envelope = build_envelope(
                event_type="order.placed",
                aggregate_type="order",
                aggregate_id=order.id,
                sequence=1,
                correlation_id=order.id,
                payload={
                    "code": order.code,
                    "customer_id": str(customer.id),
                    "items": item_lines,
                    "total_cents": order.total_cents,
                    "grid_x": address.grid_x,
                    "grid_y": address.grid_y,
                },
            )
            write_outbox_event(placed_envelope)

            subtotal = pricing.subtotal_cents(
                [(oi.unit_price_cents, oi.qty) for oi in order_items]
            )
            fee = pricing.delivery_fee_cents(subtotal, config.gateway)
            order.subtotal_cents = subtotal
            order.delivery_fee_cents = fee
            order.total_cents = pricing.total_cents(subtotal, fee)

            reason = rejection.rejection_reason(
                [menu_items_by_sku[item["sku"]] for item in payload["items"]], address, config
            )
            if reason is not None:
                order.status = apply_transition("placed", "reject")
                order.rejection_reason = reason
                order.save()
                OrderStatusEvent.objects.create(
                    order=order, from_status="placed", to_status="rejected", event="reject"
                )
                write_outbox_event(
                    build_envelope(
                        event_type="order.rejected",
                        aggregate_type="order",
                        aggregate_id=order.id,
                        sequence=2,
                        correlation_id=order.id,
                        causation_id=placed_envelope.event_id,
                        payload={"code": order.code, "reason": reason, "queue_depth": 0},
                    )
                )
                response_status = 202
            else:
                order.status = apply_transition("placed", "accept")
                order.accepted_at = timezone.now()
                order.promised_at = pricing.promised_at(order.accepted_at, get_speed())
                order.save()
                OrderStatusEvent.objects.create(
                    order=order, from_status="placed", to_status="accepted", event="accept"
                )
                accepted_envelope = build_envelope(
                    event_type="order.accepted",
                    aggregate_type="order",
                    aggregate_id=order.id,
                    sequence=2,
                    correlation_id=order.id,
                    causation_id=placed_envelope.event_id,
                    payload={
                        "code": order.code,
                        "promised_at": order.promised_at,
                        "items": item_lines,
                    },
                )
                write_outbox_event(accepted_envelope)
                response_status = 201

        if response_status == 201:
            start_progression(order, sequence=3, causation_id=str(accepted_envelope.event_id))

        order = Order.objects.prefetch_related("items").get(id=order.id)
        return Response(OrderSerializer(order).data, status=response_status)


class OrderDetailView(APIView):
    """`GET /orders/{code}` — customer(own) / manager (SPEC.md §3.1)."""

    permission_classes = [IsAuthenticated, IsOwnOrderOrManager]

    @extend_schema(responses=OrderSerializer)
    def get(self, request: Request, code: str) -> Response:
        order = get_object_or_404(Order.objects.prefetch_related("items"), code=code)
        self.check_object_permissions(request, order)
        return Response(OrderSerializer(order).data)


class OrderTimelineView(APIView):
    """`GET /orders/{code}/timeline` — ordered event history."""

    permission_classes = [IsAuthenticated, IsOwnOrderOrManager]

    @extend_schema(responses=OrderStatusEventSerializer(many=True))
    def get(self, request: Request, code: str) -> Response:
        order = get_object_or_404(Order, code=code)
        self.check_object_permissions(request, order)
        events = order.timeline.all()
        return Response(OrderStatusEventSerializer(events, many=True).data)
