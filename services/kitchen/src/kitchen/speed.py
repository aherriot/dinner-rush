"""Kitchen-side read of the runtime `SPEED` override — see
`dinner_rush_core.speed`. Kitchen never writes it (`POST /admin/speed` is
gateway's), only reads it, for the same reason every duration here is
divided by `SPEED` at the point of use rather than stored pre-scaled
(SPEC.md §5).
"""

from dinner_rush_core import speed as core_speed
from kitchen.redis_client import get_redis_client


def get_speed() -> int:
    return core_speed.get_speed(get_redis_client())
