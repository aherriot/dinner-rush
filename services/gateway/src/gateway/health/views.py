from typing import Any

import redis
from django.conf import settings
from django.db import DatabaseError, connections
from django.db.utils import OperationalError
from django.http import JsonResponse


def healthz(request: Any) -> JsonResponse:
    """Liveness: the process is up and can serve a response."""
    return JsonResponse({"status": "ok"})


def readyz(request: Any) -> JsonResponse:
    """Readiness: the gateway's own dependencies are actually reachable."""
    checks: dict[str, str] = {}
    ready = True

    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["postgres"] = "ok"
    except (OperationalError, DatabaseError) as exc:
        checks["postgres"] = f"error: {exc}"
        ready = False

    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        client.ping()
        checks["redis"] = "ok"
    except redis.RedisError as exc:
        checks["redis"] = f"error: {exc}"
        ready = False

    return JsonResponse(
        {"status": "ready" if ready else "not-ready", "checks": checks},
        status=200 if ready else 503,
    )
