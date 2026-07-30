import os
from collections.abc import Iterator

import pytest
import redis
from sqlalchemy.orm import Session

from dinner_rush_core.config import CourierSpeedConfig, DispatchConfig, GridConfig, RestaurantConfig
from dispatch.cli import run_reset, run_seed
from dispatch.geo import get_position
from dispatch.models import Courier

_DISPATCH_CONFIG = DispatchConfig(
    grid=GridConfig(width=100, height=100),
    restaurant=RestaurantConfig(x=50, y=50),
    courier_count=3,
    courier_speed_cells_per_minute=CourierSpeedConfig(bike=22, scooter=38),
    search_radius_cells=30,
    max_trips_per_courier=2,
    batch_max_detour_cells=8,
    assignment_retry_seconds=10,
    max_assignment_retry_seconds=90,
    address_grant_ttl_seconds=3600,
    eta_recalc_interval_seconds=30,
)


class _FakeRootConfig:
    dispatch = _DISPATCH_CONFIG


@pytest.fixture(autouse=True)
def _config(monkeypatch: pytest.MonkeyPatch) -> None:
    import dispatch.cli as cli_module

    monkeypatch.setattr(cli_module, "load_config", lambda: _FakeRootConfig())


@pytest.fixture
def redis_client() -> Iterator[redis.Redis]:
    client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    yield client
    client.delete("couriers:live")
    client.close()


def test_reset_re_scatters_courier_positions_into_redis(
    session: Session, redis_client: redis.Redis
) -> None:
    """`run_reset` used to `DEL couriers:live` and leave it empty, on the
    (wrong) assumption that couriers "re-report" their own position — they
    don't; nothing writes to Redis except seed and the motion autopilot, and
    the autopilot only runs once a courier already has a trip. An empty GEO
    key after reset made every courier permanently invisible to
    `GEOSEARCH`, so no order could ever find one. A reset must leave every
    courier's position populated, exactly like a fresh seed does."""
    run_seed()
    courier_ids = [str(c.id) for c in session.query(Courier).order_by(Courier.id).all()]
    assert len(courier_ids) == 3

    run_reset()

    for courier_id in courier_ids:
        position = get_position(redis_client, courier_id)
        assert position is not None, f"courier {courier_id} has no position in Redis after reset"
