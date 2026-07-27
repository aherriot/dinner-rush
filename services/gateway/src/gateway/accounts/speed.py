"""Runtime SPEED override — `POST /admin/speed` (SPEC.md §3.2).

Thin gateway-side wrapper around `dinner_rush_core.speed` — the key and
fallback logic are shared so kitchen reads the exact same runtime value
gateway's admin endpoint writes.
"""

import redis
from django.conf import settings

from dinner_rush_core import speed as core_speed

VALID_SPEEDS = core_speed.VALID_SPEEDS


def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL)


def get_speed() -> int:
    return core_speed.get_speed(_client())


def set_speed(speed: int) -> None:
    core_speed.set_speed(_client(), speed)
