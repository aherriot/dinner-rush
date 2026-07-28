"""Redis-backed state for the two override-driven chaos scenarios
(`friday_rush`, `courier_offline` — SPEC.md §3.2, PHASES.md Phase 8).

The other two controllable scenarios (`oven_down`, `ingredient_shortage`) act
through real admin endpoints instead (kitchen's oven-status write, gateway's
own menu-availability flip) and need no persisted "is it active" flag of
their own — the oven/menu state itself, already visible on the board, is the
only state that matters.

`duration_seconds` is real demo wall-clock time, never divided by SPEED
(config.example.yaml's own rule) — a Redis key `EX` is exactly that: a
wall-clock TTL. An expired key simply isn't there to read, so `SPEED`-scaled
"is this scenario still running" logic never needs to exist.
"""

import json

import redis
from django.conf import settings

_KEY_PREFIX = "scenario:override:"
OVERRIDE_SCENARIOS = ("friday_rush", "courier_offline")


def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL)


def set_override(name: str, overrides: dict[str, object], *, duration_seconds: int | None) -> None:
    client = _client()
    key = _KEY_PREFIX + name
    payload = json.dumps(overrides)
    if duration_seconds is not None:
        client.set(key, payload, ex=duration_seconds)
    else:
        client.set(key, payload)


def clear_override(name: str) -> None:
    _client().delete(_KEY_PREFIX + name)


def get_active_overrides() -> dict[str, object]:
    """Merged overrides from every scenario still live. Later entries in
    `OVERRIDE_SCENARIOS` win on key collision — there are none today, but if
    two scenarios ever override the same path this is the tie-break."""
    client = _client()
    merged: dict[str, object] = {}
    for name in OVERRIDE_SCENARIOS:
        raw = client.get(_KEY_PREFIX + name)
        if raw is not None:
            merged.update(json.loads(raw))
    return merged


def active_scenario_names() -> list[str]:
    client = _client()
    return [name for name in OVERRIDE_SCENARIOS if client.exists(_KEY_PREFIX + name)]
