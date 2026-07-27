import pytest
from django.test import Client


def test_healthz_reports_ok_without_touching_dependencies() -> None:
    response = Client().get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readyz_reports_postgres_and_redis_reachable() -> None:
    response = Client().get("/readyz")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["checks"]["postgres"] == "ok"
    assert body["checks"]["redis"] == "ok"
