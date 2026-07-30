"""The simulator's own config loader — deliberately not `dinner_rush_core`.

CLAUDE.md §5: the simulator "imports nothing from `services/`" and holds no
shared domain code; the small amount of YAML-path-walking duplicated from
`dinner_rush_core.config` here is the price of that isolation being real
rather than asserted. Only `simulator` and `scenarios` are modeled — every
other top-level key (`front_of_house`, `kitchen`, `menu`, ...) belongs to services
this process never touches and is silently dropped by `extra="ignore"`.
"""

import copy
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

_ENV_VAR = "CONFIG_PATH"
_CANDIDATE_NAMES = ("config.yaml", "config.example.yaml")
_MAX_SEARCH_DEPTH = 6

#: The only scenario whose `overrides` target something this phase's
#: simulator actually simulates (`simulator.customers.*`). `courier_offline`
#: also has `overrides`, but they're `simulator.couriers.*` — real once
#: Phase 7 gives the simulator courier behaviour to call dispatch with, a
#: no-op today. Rejecting it explicitly here is more honest than silently
#: applying an override nothing reads.
_SUPPORTED_SCENARIOS = {"friday_rush"}


class ThinkTimeConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    min: int
    max: int


class CustomersConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    arrival: str
    baseline_rate_per_minute: float
    think_time_seconds: ThinkTimeConfig
    basket_size_weights: dict[int, float]
    cancel_probability: float
    repeat_customer_probability: float
    population: int


class SimulatorConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    api_base_url: str
    dispatch_base_url: str
    customers: CustomersConfig


class ScenarioConfig(BaseModel):
    """Loose by design — `friday_rush`/`courier_offline` carry `overrides`,
    `oven_down`/`ingredient_shortage` carry `actions`, `dispatch_down` carries
    `manual`. Only `overrides` scenarios are runnable by the simulator itself
    this phase; see `simulator.scenario`."""

    model_config = ConfigDict(extra="ignore")

    description: str
    duration_seconds: int | None = None
    overrides: dict[str, object] | None = None
    actions: list[dict[str, object]] | None = None
    manual: str | None = None
    expect: str | None = None


class RootConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    simulator: SimulatorConfig
    scenarios: dict[str, ScenarioConfig] = {}


class ConfigNotFoundError(FileNotFoundError):
    pass


def resolve_config_path() -> Path:
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


def _load_raw() -> dict[str, Any]:
    with resolve_config_path().open() as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    return raw


@lru_cache(maxsize=1)
def load_config() -> RootConfig:
    return RootConfig.model_validate(_load_raw())


@dataclass(frozen=True)
class ScenarioRun:
    name: str
    description: str
    duration_seconds: int | None
    expect: str | None
    simulator: SimulatorConfig


def apply_scenario_overrides(name: str) -> ScenarioRun:
    """Patches `simulator.*` dotted-path overrides from `scenarios.<name>`
    onto a fresh copy of the raw config and reparses just the `simulator`
    block — the baseline `load_config()` (and its cache) is untouched, so a
    scenario run never leaks its overrides into anything reading config
    afterward in the same process."""
    raw = copy.deepcopy(_load_raw())
    scenario = RootConfig.model_validate(raw).scenarios.get(name)
    if scenario is None:
        raise UnknownScenarioError(f"no scenario named {name!r} in config.yaml")
    if name not in _SUPPORTED_SCENARIOS:
        reason = (
            "it has `actions`, which need front-of-house's admin scenario endpoint (Phase 10)"
            if scenario.actions
            else "it is `manual`, see config.example.yaml"
            if scenario.manual
            else "its `overrides` target simulator behaviour not implemented yet "
            "(courier_offline needs dispatch, Phase 7)"
        )
        raise UnsupportedScenarioError(
            f"scenario {name!r} isn't runnable by the simulator yet — {reason}"
        )
    assert scenario.overrides is not None  # guaranteed by _SUPPORTED_SCENARIOS membership

    for dotted_path, value in scenario.overrides.items():
        _set_dotted(raw, dotted_path, value)

    patched = RootConfig.model_validate(raw)
    return ScenarioRun(
        name=name,
        description=scenario.description,
        duration_seconds=scenario.duration_seconds,
        expect=scenario.expect,
        simulator=patched.simulator,
    )


def _set_dotted(raw: dict[str, Any], dotted_path: str, value: object) -> None:
    *parents, leaf = dotted_path.split(".")
    node = raw
    for key in parents:
        node = node[key]
    node[leaf] = value


class UnknownScenarioError(KeyError):
    pass


class UnsupportedScenarioError(NotImplementedError):
    pass
