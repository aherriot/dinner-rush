from django.urls import re_path

from front_of_house.eventing.consumers import BoardConsumer, OrderTrackerConsumer

# django-stubs types `re_path`'s view for an HTTP `HttpResponseBase` callable;
# Channels' `.as_asgi()` returns an ASGI application instead, which is the
# correct type for a websocket route but not one django-stubs models.
websocket_urlpatterns = [
    re_path(r"^ws/orders/(?P<code>[^/]+)/$", OrderTrackerConsumer.as_asgi()),  # type: ignore[arg-type]
    re_path(r"^ws/board/$", BoardConsumer.as_asgi()),  # type: ignore[arg-type]
]
