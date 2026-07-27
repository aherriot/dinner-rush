"""Django settings for the gateway service.

Phase 2: the monolith — menu, customers, orders, pricing, HS256 JWT auth with
roles, admin. See ADR 0002 for why HS256 now / RS256 JWKS in Phase 5.
"""

import datetime
import os
from pathlib import Path

from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "phase-0-insecure-dev-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "gateway.health",
    "gateway.catalog",
    "gateway.customers",
    "gateway.accounts",
    "gateway.orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "gateway.common.middleware.CorrelationIdMiddleware",
]

# Local-only: the storefront/tracker (Vite, :5173) calls the gateway (:8000)
# cross-origin. This project is never hosted (CLAUDE.md §"This is a portfolio
# project"), so an explicit dev-origin allowlist is enough — no wildcard.
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
CORS_ALLOW_HEADERS = [*default_headers, "idempotency-key"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["gateway.common.authentication.JWTRoleAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "gateway.common.exceptions.problem_detail_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": datetime.timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": datetime.timedelta(days=7),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Dinner Rush — gateway",
    "DESCRIPTION": "Public API, admin API and websocket fanout.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

ROOT_URLCONF = "gateway.urls"
ASGI_APPLICATION = "gateway.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "gateway"),
        "USER": os.environ.get("POSTGRES_USER", "gateway"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "gateway"),
        "HOST": os.environ.get("POSTGRES_HOST", "gateway-db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"

STATIC_URL = "static/"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
