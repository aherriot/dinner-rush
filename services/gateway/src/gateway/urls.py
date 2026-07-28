from django.conf import settings
from django.contrib.staticfiles.views import serve as serve_static
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

import gateway.common.schema  # noqa: F401 — registers the Bearer JWT auth scheme
from gateway.common.views import jwks

urlpatterns = [
    path("", include("gateway.health.urls")),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path(".well-known/jwks.json", jwks, name="jwks"),
    path("api/v1/", include("gateway.accounts.urls")),
    path("api/v1/", include("gateway.catalog.urls")),
    path("api/v1/", include("gateway.orders.urls")),
    path("api/v1/", include("gateway.board.urls")),
]

if settings.DEBUG:
    # DRF's own browsable API (visiting any endpoint directly in a browser)
    # needs its CSS/JS/fonts served from somewhere. `daphne` — this project's
    # ASGI server even in dev — doesn't auto-serve them the way `manage.py
    # runserver` does, so wire the same view `runserver` would use directly.
    # Dev-only: `staticfiles.views.serve` refuses outside DEBUG.
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", serve_static),
    ]
