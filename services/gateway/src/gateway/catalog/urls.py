from django.urls import path

from gateway.catalog.views import MenuAvailabilityView, MenuListView

urlpatterns = [
    path("menu", MenuListView.as_view(), name="menu-list"),
    path(
        "admin/menu/<str:sku>/availability",
        MenuAvailabilityView.as_view(),
        name="menu-availability",
    ),
]
