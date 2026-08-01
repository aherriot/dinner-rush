from dinner_rush_core.config import (
    CapacityConfig,
    CourierSpeedConfig,
    DispatchConfig,
    FrontOfHouseConfig,
    GridConfig,
    KitchenConfig,
    ObservabilityConfig,
    RestaurantConfig,
    RootConfig,
    ServiceClientConfig,
    SimulatorConfig,
    SimulatorCustomersConfig,
    StreamsConfig,
)
from front_of_house.catalog.models import MenuItem
from front_of_house.customers.models import Address
from front_of_house.orders.rejection import chebyshev_distance, rejection_reason


def _config(max_delivery_distance_cells: int = 45) -> RootConfig:
    return RootConfig(
        speed=1,
        front_of_house=FrontOfHouseConfig(
            delivery_fee_cents=299,
            free_delivery_threshold_cents=4000,
            max_delivery_distance_cells=max_delivery_distance_cells,
            order_code_start=4400,
        ),
        dispatch=DispatchConfig(
            grid=GridConfig(width=100, height=100),
            restaurant=RestaurantConfig(x=50, y=50),
            courier_count=8,
            courier_speed_cells_per_minute=CourierSpeedConfig(bike=22, scooter=38),
            search_radius_cells=30,
            max_trips_per_courier=2,
            batch_max_detour_cells=8,
            assignment_retry_seconds=10,
            max_assignment_retry_seconds=90,
            address_grant_ttl_seconds=3600,
            eta_recalc_interval_seconds=30,
        ),
        kitchen=KitchenConfig(
            ovens=[],
            stations=[],
            tick_interval_seconds=1,
            slot_reaper_interval_seconds=5,
            slot_reaper_grace_seconds=30,
            ticket_reconciler_grace_seconds=30,
            capacity=CapacityConfig(
                max_queue_depth=40,
                max_projected_wait_seconds=2700,
                promise_buffer_seconds=180,
                reject_when_all_ovens_down=True,
            ),
        ),
        menu=[],
        streams=StreamsConfig(
            maxlen=100_000,
            claim_min_idle_seconds=30,
            read_block_ms=2000,
            read_count=64,
            outbox_poll_ms=100,
            outbox_batch=100,
        ),
        service_client=ServiceClientConfig(
            timeout_seconds=5,
            retry_max_attempts=3,
            retry_base_delay_seconds=0.1,
            retry_max_delay_seconds=1.0,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_reset_seconds=30,
        ),
        simulator=SimulatorConfig(customers=SimulatorCustomersConfig(population=50)),
        observability=ObservabilityConfig(
            otel_endpoint="http://otel-collector:4317",
            trace_sample_ratio=1.0,
            metrics_port=9100,
            log_level="INFO",
            log_format="json",
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
