"""`GET /board/snapshot`, the oven-status admin proxy, and chaos scenario
start/stop (SPEC.md §3.1-3.2, PHASES.md Phase 8)."""

from typing import Any

import pytest
from rest_framework.test import APIClient

import front_of_house.board.views as board_views
from front_of_house.board import scenario_state
from front_of_house.board.scenarios_config import ScenarioActionConfig, ScenarioConfig
from front_of_house.orders import kitchen_client

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_scenario_state() -> Any:
    for name in scenario_state.OVERRIDE_SCENARIOS:
        scenario_state.clear_override(name)
    yield
    for name in scenario_state.OVERRIDE_SCENARIOS:
        scenario_state.clear_override(name)


# -- GET /board/snapshot ------------------------------------------------------


def test_board_snapshot_403s_for_a_customer(as_customer: APIClient) -> None:
    response = as_customer.get("/api/v1/board/snapshot")
    assert response.status_code == 403


def test_board_snapshot_200s_for_kitchen_and_manager(
    as_kitchen: APIClient, as_manager: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(board_views.kitchen_client, "get_queue", lambda **kw: [])
    monkeypatch.setattr(board_views.kitchen_client, "get_ovens", lambda **kw: [])
    monkeypatch.setattr(board_views.dispatch_client, "get_trips", lambda **kw: [])
    monkeypatch.setattr(board_views.dispatch_client, "get_couriers", lambda **kw: [])
    monkeypatch.setattr(board_views.dispatch_client, "get_backlog", lambda **kw: {})

    assert as_kitchen.get("/api/v1/board/snapshot").status_code == 200
    assert as_manager.get("/api/v1/board/snapshot").status_code == 200


def test_board_snapshot_includes_recent_orders_and_proxied_kitchen_dispatch_data(
    as_manager: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        board_views.kitchen_client, "get_queue", lambda **kw: [{"code": "4471"}]
    )
    monkeypatch.setattr(
        board_views.kitchen_client, "get_ovens", lambda **kw: [{"name": "Oven 1"}]
    )
    monkeypatch.setattr(
        board_views.dispatch_client, "get_trips", lambda **kw: [{"code": "4471"}]
    )
    monkeypatch.setattr(
        board_views.dispatch_client, "get_couriers", lambda **kw: [{"name": "Courier A"}]
    )
    monkeypatch.setattr(
        board_views.dispatch_client,
        "get_backlog",
        lambda **kw: {"ready_count": 3, "oldest_waiting_seconds": 912.5},
    )

    response = as_manager.get("/api/v1/board/snapshot")
    assert response.status_code == 200
    body = response.json()
    assert body["orders"] == []
    assert body["kitchen"] == {"queue": [{"code": "4471"}], "ovens": [{"name": "Oven 1"}]}
    assert body["dispatch"] == {
        "trips": [{"code": "4471"}],
        "couriers": [{"name": "Courier A"}],
        "backlog": {"ready_count": 3, "oldest_waiting_seconds": 912.5},
    }


def test_board_snapshot_degrades_to_null_sections_when_peers_are_unreachable(
    as_manager: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(board_views.kitchen_client, "get_queue", lambda **kw: None)
    monkeypatch.setattr(board_views.kitchen_client, "get_ovens", lambda **kw: None)
    monkeypatch.setattr(board_views.dispatch_client, "get_trips", lambda **kw: None)
    monkeypatch.setattr(board_views.dispatch_client, "get_couriers", lambda **kw: None)
    monkeypatch.setattr(board_views.dispatch_client, "get_backlog", lambda **kw: None)

    response = as_manager.get("/api/v1/board/snapshot")
    assert response.status_code == 200
    body = response.json()
    assert body["kitchen"] == {"queue": None, "ovens": None}
    assert body["dispatch"] == {"trips": None, "couriers": None, "backlog": None}


# -- POST /admin/ovens/{id}/status -------------------------------------------


def test_admin_oven_status_403s_for_kitchen_role(as_kitchen: APIClient) -> None:
    response = as_kitchen.post("/api/v1/admin/ovens/oven-1/status", {"status": "down"})
    assert response.status_code == 403


def test_admin_oven_status_proxies_to_kitchen(
    as_manager: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def _fake_set_status(oven_id: str, status: str, **kw: Any) -> dict[str, str]:
        calls.append((oven_id, status))
        return {"id": oven_id, "status": status}

    monkeypatch.setattr(board_views.kitchen_client, "set_oven_status", _fake_set_status)

    response = as_manager.post("/api/v1/admin/ovens/oven-1/status", {"status": "down"})
    assert response.status_code == 200
    assert response.json() == {"id": "oven-1", "status": "down"}
    assert calls == [("oven-1", "down")]


def test_admin_oven_status_rejects_an_invalid_status_value(as_manager: APIClient) -> None:
    response = as_manager.post("/api/v1/admin/ovens/oven-1/status", {"status": "on_fire"})
    assert response.status_code == 400


def test_admin_oven_status_404s_when_kitchen_reports_unknown_oven(
    as_manager: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx

    def _raise_404(*args: Any, **kwargs: Any) -> Any:
        request = httpx.Request("POST", "http://kitchen/ovens/x/status")
        raise httpx.HTTPStatusError(
            "not found", request=request, response=httpx.Response(404, request=request)
        )

    monkeypatch.setattr(board_views.kitchen_client, "set_oven_status", _raise_404)

    response = as_manager.post("/api/v1/admin/ovens/missing/status", {"status": "down"})
    assert response.status_code == 404


def test_admin_oven_status_503s_when_kitchen_is_unreachable(
    as_manager: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_unavailable(*args: Any, **kwargs: Any) -> Any:
        raise kitchen_client.KitchenUnavailableError("no route to kitchen")

    monkeypatch.setattr(board_views.kitchen_client, "set_oven_status", _raise_unavailable)

    response = as_manager.post("/api/v1/admin/ovens/oven-1/status", {"status": "down"})
    assert response.status_code == 503


# -- POST /admin/scenarios/{name}/start|stop + GET /scenarios/active --------


def _fake_scenarios(**overrides: ScenarioConfig) -> Any:
    class _Fake:
        def get(self, name: str) -> ScenarioConfig:
            return overrides[name]

    return _Fake()


def test_scenario_start_403s_for_kitchen_role(as_kitchen: APIClient) -> None:
    response = as_kitchen.post("/api/v1/admin/scenarios/friday_rush/start")
    assert response.status_code == 403


def test_scenario_start_rejects_dispatch_down(as_manager: APIClient) -> None:
    response = as_manager.post("/api/v1/admin/scenarios/dispatch_down/start")
    assert response.status_code == 400


def test_scenario_start_rejects_an_unknown_name(as_manager: APIClient) -> None:
    response = as_manager.post("/api/v1/admin/scenarios/not_a_real_scenario/start")
    assert response.status_code == 400


def test_friday_rush_start_writes_a_ttl_scoped_redis_override_the_simulator_can_poll(
    as_manager: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        board_views,
        "load_scenarios",
        lambda: _fake_scenarios(
            friday_rush=ScenarioConfig(
                description="rush",
                duration_seconds=120,
                overrides={"simulator.customers.baseline_rate_per_minute": 18},
            )
        ),
    )

    response = as_manager.post("/api/v1/admin/scenarios/friday_rush/start")
    assert response.status_code == 200
    assert response.json()["overrides"] == {
        "simulator.customers.baseline_rate_per_minute": 18
    }

    # `GET /scenarios/active` is public/unauthenticated (mirrors GET /speed) —
    # the simulator has no service credentials to call it any other way.
    active = APIClient().get("/api/v1/scenarios/active")
    assert active.status_code == 200
    assert active.json() == {
        "overrides": {"simulator.customers.baseline_rate_per_minute": 18},
        "scenarios": ["friday_rush"],
    }

    stop = as_manager.post("/api/v1/admin/scenarios/friday_rush/stop")
    assert stop.status_code == 200
    active_after_stop = APIClient().get("/api/v1/scenarios/active")
    assert active_after_stop.json() == {"overrides": {}, "scenarios": []}


def test_oven_down_start_resolves_the_configured_oven_name_and_flips_it(
    as_manager: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        board_views,
        "load_scenarios",
        lambda: _fake_scenarios(
            oven_down=ScenarioConfig(
                description="oven down",
                duration_seconds=300,
                actions=[
                    ScenarioActionConfig(
                        at_seconds=0,
                        call="POST /admin/ovens/{oven_3}/status",
                        body={"status": "down"},
                    ),
                    ScenarioActionConfig(
                        at_seconds=300,
                        call="POST /admin/ovens/{oven_3}/status",
                        body={"status": "available"},
                    ),
                ],
            )
        ),
    )
    monkeypatch.setattr(
        board_views.kitchen_client,
        "get_ovens",
        lambda **kw: [{"id": "real-oven-id", "name": "Oven 3"}],
    )
    calls = []
    monkeypatch.setattr(
        board_views.kitchen_client,
        "set_oven_status",
        lambda oven_id, status, **kw: calls.append((oven_id, status)) or {},
    )

    start = as_manager.post("/api/v1/admin/scenarios/oven_down/start")
    assert start.status_code == 200
    assert calls == [("real-oven-id", "down")]

    stop = as_manager.post("/api/v1/admin/scenarios/oven_down/stop")
    assert stop.status_code == 200
    assert calls == [("real-oven-id", "down"), ("real-oven-id", "available")]


def test_ingredient_shortage_start_and_stop_flip_menu_availability(
    as_manager: APIClient, monkeypatch: pytest.MonkeyPatch, menu_item: Any
) -> None:
    monkeypatch.setattr(
        board_views,
        "load_scenarios",
        lambda: _fake_scenarios(
            ingredient_shortage=ScenarioConfig(
                description="shortage",
                duration_seconds=240,
                actions=[
                    ScenarioActionConfig(
                        at_seconds=0,
                        call=f"POST /admin/menu/{menu_item.sku}/availability",
                        body={"available": False},
                    ),
                    ScenarioActionConfig(
                        at_seconds=240,
                        call=f"POST /admin/menu/{menu_item.sku}/availability",
                        body={"available": True},
                    ),
                ],
            )
        ),
    )

    start = as_manager.post("/api/v1/admin/scenarios/ingredient_shortage/start")
    assert start.status_code == 200
    menu_item.refresh_from_db()
    assert menu_item.available is False

    stop = as_manager.post("/api/v1/admin/scenarios/ingredient_shortage/stop")
    assert stop.status_code == 200
    menu_item.refresh_from_db()
    assert menu_item.available is True


def test_scenarios_active_requires_no_auth() -> None:
    # Not gated behind any permission class at all — sanity check it's public.
    response = APIClient().get("/api/v1/scenarios/active")
    assert response.status_code == 200
