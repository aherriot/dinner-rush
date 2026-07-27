from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from gateway.common.authentication import get_actor


class IsCustomer(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return get_actor(request).role == "customer"


class IsManager(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return get_actor(request).role == "manager"


class IsOwnOrderOrManager(BasePermission):
    """SPEC.md §6.1 — a customer sees only their own order; a manager sees any."""

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        actor = get_actor(request)
        if actor.role == "manager":
            return True
        return actor.role == "customer" and str(obj.customer_id) == actor.customer_id
