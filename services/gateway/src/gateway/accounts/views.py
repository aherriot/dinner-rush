from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from gateway.accounts.models import Staff
from gateway.accounts.serializers import (
    CustomerTokenRequestSerializer,
    SpeedSerializer,
    StaffTokenRequestSerializer,
    TokenRequestSerializer,
    TokenResponseSerializer,
)
from gateway.accounts.speed import VALID_SPEEDS, get_speed, set_speed
from gateway.common.authentication import get_actor
from gateway.common.permissions import IsManager
from gateway.customers.models import Customer
from gateway.customers.serializers import CustomerSerializer

#: SPEC.md §6.1's resource matrix, encoded as scope strings. Gateway's own
#: DRF permission classes (`IsManager`, ...) still authorize on `role` — this
#: is the claim kitchen/dispatch check instead, since they have no view of
#: gateway's role-to-permission mapping and shouldn't need one.
ROLE_SCOPES: dict[str, list[str]] = {
    "customer": ["orders:own"],
    "kitchen": ["kitchen:read", "kitchen:advance"],
    "manager": ["orders:any", "kitchen:read", "kitchen:advance", "admin:all", "analytics:read"],
}


def _issue_token(*, role: str, **claims: str) -> dict[str, str]:
    refresh = RefreshToken()
    refresh["role"] = role
    refresh["scope"] = ROLE_SCOPES[role]
    refresh["sub"] = claims.get("customer_id") or claims.get("staff_id") or role
    for key, value in claims.items():
        refresh[key] = value
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class TokenView(APIView):
    """`POST /auth/token` (SPEC.md §3.1).

    Staff (kitchen/manager) authenticate with `username`+`password` against
    `django.contrib.auth`. Customers authenticate with just their seeded
    `email` — there is no signup flow in this phase and the customer table
    has no credentials of its own (SPEC.md §1.1); see ADR 0002.
    """

    permission_classes = []
    authentication_classes = []

    @extend_schema(request=TokenRequestSerializer, responses=TokenResponseSerializer)
    def post(self, request: Request) -> Response:
        if "password" in request.data:
            staff_request = StaffTokenRequestSerializer(data=request.data)
            staff_request.is_valid(raise_exception=True)
            user = authenticate(
                username=staff_request.validated_data["username"],
                password=staff_request.validated_data["password"],
            )
            if user is None:
                raise AuthenticationFailed("invalid username or password")
            try:
                staff = Staff.objects.get(user=user)
            except Staff.DoesNotExist as exc:
                raise AuthenticationFailed("user is not staff") from exc
            return Response(_issue_token(role=staff.role, staff_id=str(staff.id)))

        if "email" in request.data:
            customer_request = CustomerTokenRequestSerializer(data=request.data)
            customer_request.is_valid(raise_exception=True)
            try:
                customer = Customer.objects.get(email=customer_request.validated_data["email"])
            except Customer.DoesNotExist as exc:
                raise AuthenticationFailed("unknown customer email") from exc
            return Response(_issue_token(role="customer", customer_id=str(customer.id)))

        raise ValidationError("expected either {email} or {username, password}")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CustomerSerializer)
    def get(self, request: Request) -> Response:
        actor = get_actor(request)
        if actor.role == "customer":
            assert actor.customer_id is not None  # guaranteed by TokenView at issuance
            customer = Customer.objects.get(id=actor.customer_id)
            return Response({"role": "customer", **CustomerSerializer(customer).data})

        assert actor.staff_id is not None  # guaranteed by TokenView at issuance
        staff = Staff.objects.get(id=actor.staff_id)
        return Response({"role": staff.role, "id": str(staff.id), "name": staff.name})


class AdminSpeedView(APIView):
    """`POST /admin/speed` (SPEC.md §3.2) — manager only."""

    permission_classes = [IsManager]

    @extend_schema(request=SpeedSerializer, responses=SpeedSerializer)
    def post(self, request: Request) -> Response:
        serializer = SpeedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        speed = serializer.validated_data["speed"]
        if speed not in VALID_SPEEDS:
            raise ValidationError(f"speed must be one of {VALID_SPEEDS}")
        set_speed(speed)
        return Response({"speed": speed})


class SpeedView(APIView):
    """`GET /speed` — read-only, unauthenticated.

    The no-virtual-clock rule (SPEC.md §5) applies to every client that
    schedules a domain-time delay, not just services — the simulator's think
    times and dwell times must divide by the live `SPEED` at the point of use
    same as everything else, and it has no privileged scope to call the
    manager-only `POST /admin/speed` to find out what that value is. The
    current speed isn't sensitive, so this is open rather than routed through
    a scope that would misrepresent it as one.
    """

    permission_classes = []
    authentication_classes = []

    @extend_schema(responses=SpeedSerializer)
    def get(self, request: Request) -> Response:
        return Response({"speed": get_speed()})
