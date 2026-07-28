"""Reads `config.example.yaml`'s `scenarios:` block for the board's chaos
controls (SPEC.md §3.2, PHASES.md Phase 8).

Deliberately **not** added to `dinner_rush_core.config.RootConfig` — that
module's own docstring leaves `scenarios:` unmodeled "until the phase that
consumes them" precisely so a consumer models only what it needs, the same
reason the simulator keeps its own separate `scenarios` parser instead of a
shared one (CLAUDE.md §5). Gateway is the only service that needs this block
this phase, so it gets its own small loader rather than growing every
service's shared config surface for one consumer.
"""

from functools import lru_cache

import yaml
from pydantic import BaseModel, ConfigDict

from dinner_rush_core.config import resolve_config_path

#: `dispatch_down` is deliberately excluded — its config entry is
#: `manual: "docker compose stop dispatch..."` with no `overrides`/`actions`
#: at all, so there is nothing for a button to start or stop.
CONTROLLABLE_SCENARIOS = ("friday_rush", "oven_down", "courier_offline", "ingredient_shortage")


class ScenarioActionConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    at_seconds: int
    call: str
    body: dict[str, object]


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str
    duration_seconds: int | None = None
    overrides: dict[str, object] = {}
    actions: list[ScenarioActionConfig] = []
    manual: str | None = None
    expect: str | None = None


class ScenariosConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    friday_rush: ScenarioConfig
    oven_down: ScenarioConfig
    courier_offline: ScenarioConfig
    ingredient_shortage: ScenarioConfig
    dispatch_down: ScenarioConfig

    def get(self, name: str) -> ScenarioConfig:
        try:
            value = getattr(self, name)
        except AttributeError as exc:
            raise UnknownScenarioError(name) from exc
        if not isinstance(value, ScenarioConfig):  # pragma: no cover - defensive
            raise UnknownScenarioError(name)
        return value


class UnknownScenarioError(KeyError):
    pass


@lru_cache(maxsize=1)
def load_scenarios() -> ScenariosConfig:
    path = resolve_config_path()
    with path.open() as f:
        raw = yaml.safe_load(f)
    return ScenariosConfig.model_validate(raw["scenarios"])
