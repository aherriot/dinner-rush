"""Redis GEO for courier positions (SPEC.md §1.3) — nothing here is durable;
a restart with an empty Redis just means every courier re-reports its
position on its next tick. Postgres (`Courier.status`) stays authoritative
for availability, same "Redis caches, Postgres decides" split DECISIONS.md
§0002 uses for oven slots.

The abstract 100x100 grid (DESIGN.md §10) isn't valid lon/lat on its own —
`GEOADD` requires latitude in ±85.05°, and our grid's y-axis runs 0-100 — so
`_to_lonlat`/`_to_grid` rescale it into a valid, invertible range. Redis then
measures *real* (haversine) distance, which doesn't equal Chebyshev grid
distance, so `nearest_within_radius` uses `GEOSEARCH` only as a generous
geographic pre-filter (never tight enough to exclude a real candidate) and
recomputes the exact Chebyshev distance in Python for the actual radius cut
and sort order. `chebyshev` is what §5's `drive_estimate_s` formula and every
ETA in this service are computed from.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from redis import Redis

COURIERS_GEO_KEY = "couriers:live"

# Conservative km-per-grid-cell upper bound for the GEOSEARCH pre-filter
# (see module docstring) — larger than either axis's true scale so the
# radius search never falsely excludes a candidate the exact Chebyshev
# check would have kept.
_KM_PER_CELL_UPPER_BOUND = 200.0
_LAT_SCALE = 1.7  # keeps y in [0, 100] within GEOADD's +/-85.05 latitude bound


def _to_lonlat(x: float, y: float) -> tuple[float, float]:
    return (x - 50.0, (y - 50.0) * _LAT_SCALE)


def _to_grid(lon: float, lat: float) -> tuple[int, int]:
    return (round(lon + 50.0), round(lat / _LAT_SCALE + 50.0))


def chebyshev(x1: int, y1: int, x2: int, y2: int) -> int:
    return max(abs(x1 - x2), abs(y1 - y2))


def set_position(client: "Redis", courier_id: str, x: int, y: int) -> None:
    lon, lat = _to_lonlat(x, y)
    client.geoadd(COURIERS_GEO_KEY, (lon, lat, courier_id))


def get_position(client: "Redis", courier_id: str) -> tuple[int, int] | None:
    raw = client.geopos(COURIERS_GEO_KEY, courier_id)
    coords = cast(list[tuple[float, float] | None], raw)
    if not coords or coords[0] is None:
        return None
    lon, lat = coords[0]
    return _to_grid(float(lon), float(lat))


@dataclass(frozen=True)
class NearbyCourier:
    courier_id: str
    x: int
    y: int
    distance_cells: int


def nearest_within_radius(
    client: "Redis", origin_x: int, origin_y: int, radius_cells: int
) -> list[NearbyCourier]:
    """Every live position within `radius_cells` Chebyshev cells of the
    origin, nearest first. Callers still filter by Postgres `Courier.status`
    themselves — Redis only knows where a courier last reported, not whether
    it's free."""
    lon, lat = _to_lonlat(origin_x, origin_y)
    raw = client.geosearch(
        COURIERS_GEO_KEY,
        longitude=lon,
        latitude=lat,
        radius=radius_cells * _KM_PER_CELL_UPPER_BOUND,
        unit="km",
        withcoord=True,
        sort="ASC",
    )
    entries = cast(list[tuple[bytes | str, tuple[float, float]]], raw)

    results: list[NearbyCourier] = []
    for member, (member_lon, member_lat) in entries:
        courier_id = member.decode() if isinstance(member, bytes) else member
        gx, gy = _to_grid(member_lon, member_lat)
        distance = chebyshev(origin_x, origin_y, gx, gy)
        if distance <= radius_cells:
            results.append(
                NearbyCourier(courier_id=courier_id, x=gx, y=gy, distance_cells=distance)
            )
    results.sort(key=lambda c: c.distance_cells)
    return results
