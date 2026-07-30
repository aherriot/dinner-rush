"""Rejection reasons (SPEC.md §1.1).

`item_unavailable`/`outside_range` are free — no network call, checked
first. `at_capacity` needs kitchen's `POST /capacity/quote` (Phase 4), so
it's a separate function: no reason to make that call if a free check
already rejected the order.
"""

from dinner_rush_core.config import RootConfig
from front_of_house.catalog.models import MenuItem
from front_of_house.customers.models import Address
from front_of_house.orders.kitchen_client import CapacityQuote


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
    if distance > config.front_of_house.max_delivery_distance_cells:
        return "outside_range"

    return None


def capacity_rejection_reason(quote: CapacityQuote) -> str | None:
    return None if quote.can_accept else "at_capacity"
