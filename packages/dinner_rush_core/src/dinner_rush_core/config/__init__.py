"""config.yaml loader and SPEED handling.

Models only the sections a service needs today (`speed`, `gateway`, `menu`,
plus `dispatch.restaurant` — the fixed origin point the gateway needs for its
own `outside_range` distance check before dispatch exists). Other top-level
keys (kitchen, the rest of dispatch, simulator, scenarios, ...) are left
unmodeled until the phase that consumes them — see PHASES.md.
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


class DispatchConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    restaurant: RestaurantConfig


class StreamsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    maxlen: int
    claim_min_idle_seconds: int
    read_block_ms: int
    read_count: int
    outbox_poll_ms: int
    outbox_batch: int


class RootConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    speed: int
    gateway: GatewayConfig
    dispatch: DispatchConfig
    menu: list[MenuItemConfig]
    streams: StreamsConfig


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
