"""Runtime SPEED override (SPEC.md §3.2, §5).

`config.yaml`'s `speed` is the boot-time default; `POST /admin/speed`
(front-of-house) changes it live by writing this key, and every service that
divides a duration by SPEED reads it from here first — one key, shared over
the same Redis every service already connects to, so a runtime change is
instant everywhere rather than requiring a restart or a per-service copy.
"""

from typing import TYPE_CHECKING

from dinner_rush_core.config import load_config

if TYPE_CHECKING:
    from redis import Redis

SPEED_KEY = "dinner_rush:speed"
VALID_SPEEDS = (1, 10, 60)


def get_speed(client: "Redis") -> int:
    value = client.get(SPEED_KEY)
    if value is not None:
        return int(value)
    return load_config().speed


def set_speed(client: "Redis", speed: int) -> None:
    client.set(SPEED_KEY, speed)
