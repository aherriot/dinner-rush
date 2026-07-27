"""Runtime SPEED override — `POST /admin/speed` (SPEC.md §3.2).

`config.yaml`'s `speed` is the boot-time default; a manager can change it live
via the admin endpoint. Stored in Redis (not Postgres) because it's a runtime
knob, not domain state, and every service that later reads it (kitchen,
dispatch) shares the same Redis. Durations are still divided by this value
only at the point of use — never stored pre-scaled (SPEC.md §5).
"""

import redis
from django.conf import settings

from dinner_rush_core.config import load_config

_SPEED_KEY = "dinner_rush:speed"
VALID_SPEEDS = (1, 10, 60)


def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL)


def get_speed() -> int:
    value = _client().get(_SPEED_KEY)
    if value is not None:
        return int(value)
    return load_config().speed


def set_speed(speed: int) -> None:
    _client().set(_SPEED_KEY, speed)
