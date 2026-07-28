from collections.abc import Iterator

import pytest
from django.test import Client

from dinner_rush_core.speed import SPEED_KEY
from gateway.accounts.speed import set_speed
from gateway.eventing.redis_client import get_redis_client


@pytest.fixture(autouse=True)
def _no_speed_override() -> Iterator[None]:
    """The speed key lives in shared Redis, not a per-test transaction — clear
    it so this file's expectations don't depend on what ran before it."""
    get_redis_client().delete(SPEED_KEY)
    yield
    get_redis_client().delete(SPEED_KEY)


def test_get_speed_needs_no_auth_and_defaults_to_one() -> None:
    response = Client().get("/api/v1/speed")
    assert response.status_code == 200
    assert response.json() == {"speed": 1}


def test_get_speed_reflects_a_prior_admin_change() -> None:
    set_speed(10)
    response = Client().get("/api/v1/speed")
    assert response.json() == {"speed": 10}
