"""config.yaml loader and SPEED handling.

Models only the sections a service needs today (`speed`, `gateway`, `menu`,
plus `dispatch.restaurant` — the fixed origin point the gateway needs for its
own `outside_range` distance check before dispatch exists). `simulator` is
modeled down to exactly one field (`customers.population`, for gateway's seed
command) — the simulator service itself never imports this module and has
its own, separate config loader for the full `simulator`/`scenarios` blocks
(CLAUDE.md §5: no shared domain imports). Other top-level keys (the rest of
dispatch, scenarios, ...) are left unmodeled until the phase that consumes
them — see PHASES.md.
"""

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

_ENV_VAR = "CONFIG_PATH"
_CANDIDATE_NAMES = ("config.yaml", "config.example.yaml")
_MAX_SEARCH_DEPTH = 6


class MenuItemConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku: str
    name: str
    price_cents: int
    prep_seconds: int
    bake_seconds: int
    oven_slots: int


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    delivery_fee_cents: int
    free_delivery_threshold_cents: int
    max_delivery_distance_cells: int
    order_code_start: int


class RestaurantConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    x: int
    y: int


class GridConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    width: int
    height: int


class CourierSpeedConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bike: float
    scooter: float


class DispatchConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    grid: GridConfig
    restaurant: RestaurantConfig
    courier_count: int
    courier_speed_cells_per_minute: CourierSpeedConfig
    search_radius_cells: int
    max_trips_per_courier: int
    batch_max_detour_cells: int
    assignment_retry_seconds: int
    max_assignment_retry_seconds: int
    address_grant_ttl_seconds: int
    eta_recalc_interval_seconds: int


class ServiceClientConfig(BaseModel):
    """Tunables for every cross-service HTTP call (PHASES.md Phase 5) — kept
    generic (not `kitchen_client`-specific) since dispatch needs the same
    shape in Phase 7."""

    model_config = ConfigDict(extra="ignore")

    timeout_seconds: float
    retry_max_attempts: int
    retry_base_delay_seconds: float
    retry_max_delay_seconds: float
    circuit_breaker_failure_threshold: int
    circuit_breaker_reset_seconds: float


class StreamsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    maxlen: int
    claim_min_idle_seconds: int
    read_block_ms: int
    read_count: int
    outbox_poll_ms: int
    outbox_batch: int


class OvenConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    slot_count: int


class StationConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    kind: str
    capacity: int


class CapacityConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    max_queue_depth: int
    max_projected_wait_seconds: int
    promise_buffer_seconds: int
    reject_when_all_ovens_down: bool


class KitchenConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ovens: list[OvenConfig]
    stations: list[StationConfig]
    tick_interval_seconds: int
    slot_reaper_interval_seconds: int
    slot_reaper_grace_seconds: int
    ticket_reconciler_grace_seconds: int
    capacity: CapacityConfig


class SimulatorCustomersConfig(BaseModel):
    """Only the one field gateway's seed command needs — the simulator itself
    reads the full `simulator`/`scenarios` blocks with its own, unshared
    config loader (CLAUDE.md §5: no shared domain imports)."""

    model_config = ConfigDict(extra="ignore")

    population: int


class SimulatorConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    customers: SimulatorCustomersConfig


class RootConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    speed: int
    gateway: GatewayConfig
    dispatch: DispatchConfig
    kitchen: KitchenConfig
    menu: list[MenuItemConfig]
    streams: StreamsConfig
    service_client: ServiceClientConfig
    simulator: SimulatorConfig


class ConfigNotFoundError(FileNotFoundError):
    pass


def resolve_config_path() -> Path:
    """Env var first, then config.yaml/config.example.yaml walking up from cwd."""
    env_path = os.environ.get(_ENV_VAR)
    if env_path:
        return Path(env_path)

    directory = Path.cwd()
    for _ in range(_MAX_SEARCH_DEPTH):
        for name in _CANDIDATE_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
        if directory.parent == directory:
            break
        directory = directory.parent

    raise ConfigNotFoundError(
        f"no config.yaml or config.example.yaml found above {Path.cwd()} "
        f"(set {_ENV_VAR} to override)"
    )


@lru_cache(maxsize=1)
def load_config() -> RootConfig:
    path = resolve_config_path()
    with path.open() as f:
        raw = yaml.safe_load(f)
    return RootConfig.model_validate(raw)
