from django.urls import path

from gateway.orders.views import OrderCreateView, OrderDetailView, OrderTimelineView

urlpatterns = [
    path("orders", OrderCreateView.as_view(), name="order-create"),
    path("orders/<str:code>", OrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:code>/timeline", OrderTimelineView.as_view(), name="order-timeline"),
]
