"""Rejection reasons reachable without a kitchen service (SPEC.md §1.1).

`at_capacity` needs `POST /capacity/quote` (Phase 4) and is unreachable here —
every order is accepted for capacity purposes in Phase 2.
"""

from dinner_rush_core.config import RootConfig
from gateway.catalog.models import MenuItem
from gateway.customers.models import Address


def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    return max(abs(x1 - x2), abs(y1 - y2))


def rejection_reason(
    menu_items: list[MenuItem], address: Address, config: RootConfig
) -> str | None:
    if any(not item.available for item in menu_items):
        return "item_unavailable"

    distance = chebyshev_distance(
        address.grid_x, address.grid_y, config.dispatch.restaurant.x, config.dispatch.restaurant.y
    )
    if distance > config.gateway.max_delivery_distance_cells:
        return "outside_range"

    return None
