from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

import gateway.common.schema  # noqa: F401 — registers the Bearer JWT auth scheme
from gateway.common.views import jwks

urlpatterns = [
    path("", include("gateway.health.urls")),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path(".well-known/jwks.json", jwks, name="jwks"),
    path("api/v1/", include("gateway.accounts.urls")),
    path("api/v1/", include("gateway.catalog.urls")),
    path("api/v1/", include("gateway.orders.urls")),
]
