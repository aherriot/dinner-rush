from dinner_rush_core.config import (
    DispatchConfig,
    GatewayConfig,
    RestaurantConfig,
    RootConfig,
    StreamsConfig,
)
from gateway.catalog.models import MenuItem
from gateway.customers.models import Address
from gateway.orders.rejection import chebyshev_distance, rejection_reason


def _config(max_delivery_distance_cells: int = 45) -> RootConfig:
    return RootConfig(
        speed=1,
        gateway=GatewayConfig(
            delivery_fee_cents=299,
            free_delivery_threshold_cents=4000,
            max_delivery_distance_cells=max_delivery_distance_cells,
            order_code_start=4400,
        ),
        dispatch=DispatchConfig(restaurant=RestaurantConfig(x=50, y=50)),
        menu=[],
        streams=StreamsConfig(
            maxlen=100_000,
            claim_min_idle_seconds=30,
            read_block_ms=2000,
            read_count=64,
            outbox_poll_ms=100,
            outbox_batch=100,
        ),
    )


def _menu_item(*, available: bool) -> MenuItem:
    return MenuItem(
        sku="MARG",
        name="Margherita",
        base_price_cents=1200,
        prep_seconds=90,
        bake_seconds=420,
        available=available,
    )


def test_chebyshev_distance_is_the_max_of_the_two_axis_deltas() -> None:
    assert chebyshev_distance(0, 0, 3, 5) == 5
    assert chebyshev_distance(10, 10, 10, 10) == 0


def test_unavailable_item_is_rejected_regardless_of_distance() -> None:
    address = Address(grid_x=50, grid_y=50)
    assert rejection_reason([_menu_item(available=False)], address, _config()) == (
        "item_unavailable"
    )


def test_address_beyond_max_distance_is_rejected() -> None:
    address = Address(grid_x=0, grid_y=0)
    assert rejection_reason([_menu_item(available=True)], address, _config()) == "outside_range"


def test_available_items_within_range_are_accepted() -> None:
    address = Address(grid_x=50, grid_y=50)
    assert rejection_reason([_menu_item(available=True)], address, _config()) is None


def test_distance_exactly_at_the_limit_is_accepted() -> None:
    address = Address(grid_x=95, grid_y=50)  # distance 45, limit 45
    assert rejection_reason([_menu_item(available=True)], address, _config()) is None
