"""The board's REST surface (SPEC.md §3.1-3.2): cold-load snapshot, the
oven-status admin proxy, and chaos scenario start/stop. Live updates after
the snapshot come from `WS /ws/board` (`gateway/eventing/consumers.py`)."""

import httpx
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from gateway.board import scenario_state
from gateway.board.scenarios_config import (
    CONTROLLABLE_SCENARIOS,
    ScenarioActionConfig,
    ScenarioConfig,
    load_scenarios,
)
from gateway.board.serializers import (
    BoardSnapshotSerializer,
    OvenStatusSerializer,
    ScenariosActiveSerializer,
    ScenarioToggleSerializer,
)
from gateway.catalog.models import MenuItem
from gateway.common.permissions import IsKitchenOrManager, IsManager
from gateway.orders import dispatch_client, kitchen_client
from gateway.orders.models import Order

BOARD_ORDER_FEED_LIMIT = 100


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "a required upstream service is unavailable"
    default_code = "service_unavailable"


class BoardSnapshotView(APIView):
    """`GET /board/snapshot` — kitchen/manager only. Kitchen/dispatch
    sections are `None` when that service didn't answer: a degraded panel,
    not a failed request — the same "keep gateway working when a peer
    isn't" story as order acceptance's capacity-quote fallback, and the
    whole point of Streams over pub/sub for Phase 10's recovery demo."""

    permission_classes = [IsKitchenOrManager]

    @extend_schema(responses=BoardSnapshotSerializer)
    def get(self, request: Request) -> Response:
        correlation_id = getattr(request, "correlation_id", None)
        orders = Order.objects.prefetch_related("items")[:BOARD_ORDER_FEED_LIMIT]
        data = {
            "orders": orders,
            "kitchen": {
                "queue": kitchen_client.get_queue(correlation_id=correlation_id),
                "ovens": kitchen_client.get_ovens(correlation_id=correlation_id),
            },
            "dispatch": {
                "trips": dispatch_client.get_trips(correlation_id=correlation_id),
                "couriers": dispatch_client.get_couriers(correlation_id=correlation_id),
            },
        }
        return Response(BoardSnapshotSerializer(data).data)


class AdminOvenStatusView(APIView):
    """`POST /admin/ovens/{id}/status` (SPEC.md §3.2) — manager only. Proxies
    to kitchen's write endpoint via a minted service token; the oven-down
    chaos button's write path."""

    permission_classes = [IsManager]

    @extend_schema(request=OvenStatusSerializer, responses=OvenStatusSerializer)
    def post(self, request: Request, oven_id: str) -> Response:
        serializer = OvenStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        correlation_id = getattr(request, "correlation_id", None)
        try:
            result = kitchen_client.set_oven_status(
                oven_id, serializer.validated_data["status"], correlation_id=correlation_id
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise NotFound("oven not found") from exc
            raise ValidationError(_error_detail(exc)) from exc
        except kitchen_client.KitchenUnavailableError as exc:
            raise ServiceUnavailable("kitchen is unavailable") from exc
        return Response(result)


class AdminScenarioStartView(APIView):
    """`POST /admin/scenarios/{name}/start` (SPEC.md §3.2) — manager only.

    Override-driven scenarios (`friday_rush`, `courier_offline`) write their
    parameter deltas to Redis with a wall-clock TTL for the simulator to
    poll (`GET /scenarios/active`). Action-driven scenarios (`oven_down`,
    `ingredient_shortage`) instead execute their `at_seconds: 0` actions
    immediately — the revert actions run on `.../stop`. `dispatch_down` has
    no `overrides`/`actions` in config at all (it's `manual:`) and is
    rejected here on purpose; it stays a `docker compose stop dispatch` demo
    step, not a button.
    """

    permission_classes = [IsManager]

    @extend_schema(request=None, responses=ScenarioToggleSerializer)
    def post(self, request: Request, name: str) -> Response:
        scenario = _get_controllable_scenario(name)
        correlation_id = getattr(request, "correlation_id", None)

        if scenario.overrides:
            scenario_state.set_override(
                name, scenario.overrides, duration_seconds=scenario.duration_seconds
            )

        applied = [
            _execute_action(action, correlation_id=correlation_id)
            for action in scenario.actions
            if action.at_seconds == 0
        ]

        return Response(
            {
                "scenario": name,
                "active": True,
                "overrides": scenario.overrides,
                "actions_applied": applied,
            }
        )


class AdminScenarioStopView(APIView):
    """`POST /admin/scenarios/{name}/stop` (SPEC.md §3.2) — manager only.
    Clears any Redis override early and runs the scenario's revert actions
    (the `at_seconds > 0` entries) immediately rather than waiting out
    `duration_seconds`."""

    permission_classes = [IsManager]

    @extend_schema(request=None, responses=ScenarioToggleSerializer)
    def post(self, request: Request, name: str) -> Response:
        scenario = _get_controllable_scenario(name)
        correlation_id = getattr(request, "correlation_id", None)

        if scenario.overrides:
            scenario_state.clear_override(name)

        applied = [
            _execute_action(action, correlation_id=correlation_id)
            for action in scenario.actions
            if action.at_seconds > 0
        ]

        return Response(
            {
                "scenario": name,
                "active": False,
                "overrides": scenario.overrides,
                "actions_applied": applied,
            }
        )


class ScenariosActiveView(APIView):
    """`GET /scenarios/active` — public, unauthenticated, mirrors
    `accounts.views.SpeedView`: the simulator has no service credentials and
    no privileged scope (CLAUDE.md §5), so a public poll is the only channel
    it has to learn which overrides currently apply."""

    permission_classes = []
    authentication_classes = []

    @extend_schema(responses=ScenariosActiveSerializer)
    def get(self, request: Request) -> Response:
        return Response(
            {
                "overrides": scenario_state.get_active_overrides(),
                "scenarios": scenario_state.active_scenario_names(),
            }
        )


def _get_controllable_scenario(name: str) -> ScenarioConfig:
    if name not in CONTROLLABLE_SCENARIOS:
        raise ValidationError(
            f"scenario {name!r} is not controllable here — expected one of {CONTROLLABLE_SCENARIOS}"
        )
    return load_scenarios().get(name)


def _execute_action(
    action: ScenarioActionConfig, *, correlation_id: str | None
) -> dict[str, object]:
    method, _, path = action.call.partition(" ")
    if method != "POST":  # pragma: no cover - config is trusted, this is a guardrail
        raise ValidationError(f"unsupported scenario action {action.call!r}")

    if path.startswith("/admin/ovens/"):
        token = path.split("/")[3]
        oven_name = _oven_name_for_token(token)
        oven_id = _resolve_oven_id(oven_name, correlation_id=correlation_id)
        status_value = str(action.body["status"])
        kitchen_client.set_oven_status(oven_id, status_value, correlation_id=correlation_id)
        return {"oven": oven_name, "status": status_value}

    if path.startswith("/admin/menu/"):
        sku = path.split("/")[3]
        available = bool(action.body["available"])
        MenuItem.objects.filter(sku=sku).update(available=available)
        return {"sku": sku, "available": available}

    raise ValidationError(f"unsupported scenario action {action.call!r}")


def _oven_name_for_token(token: str) -> str:
    """`{oven_3}` (config.example.yaml's placeholder) -> `"Oven 3"` (the
    `name` kitchen's seed command gives that oven, from `kitchen.ovens` in
    the same config file)."""
    stripped = token.strip("{}")
    prefix, _, number = stripped.partition("_")
    return f"{prefix.capitalize()} {number}"


def _resolve_oven_id(oven_name: str, *, correlation_id: str | None) -> str:
    ovens = kitchen_client.get_ovens(correlation_id=correlation_id)
    if ovens is None:
        raise ServiceUnavailable("kitchen is unavailable")
    for oven in ovens:
        if oven.get("name") == oven_name:
            return str(oven["id"])
    raise ValidationError(f"no oven named {oven_name!r}")


def _error_detail(exc: httpx.HTTPStatusError) -> str:
    try:
        body = exc.response.json()
    except ValueError:
        return str(exc)
    detail = body.get("detail") if isinstance(body, dict) else None
    return str(detail) if detail is not None else str(exc)
