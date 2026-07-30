from django.urls import path

from front_of_house.board.views import (
    AdminOvenStatusView,
    AdminScenarioStartView,
    AdminScenarioStopView,
    BoardSnapshotView,
    ScenariosActiveView,
)

urlpatterns = [
    path("board/snapshot", BoardSnapshotView.as_view(), name="board-snapshot"),
    path(
        "admin/ovens/<str:oven_id>/status",
        AdminOvenStatusView.as_view(),
        name="admin-oven-status",
    ),
    path(
        "admin/scenarios/<str:name>/start",
        AdminScenarioStartView.as_view(),
        name="admin-scenario-start",
    ),
    path(
        "admin/scenarios/<str:name>/stop",
        AdminScenarioStopView.as_view(),
        name="admin-scenario-stop",
    ),
    path("scenarios/active", ScenariosActiveView.as_view(), name="scenarios-active"),
]
