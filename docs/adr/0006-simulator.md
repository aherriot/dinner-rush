# 0006 — The simulator: isolation, Poisson arrivals, and scenario scope

## Status

Accepted.

## Context

Phase 6 (PHASES.md) is the phase that pays off Phase 0's premise: a genuine
API client generating real concurrent load, not a script that calls internal
functions. CLAUDE.md §5 sets the constraints structurally — no service or
database credentials, no shared domain imports, its own dependency file,
network-restricted to public API ports — and SPEC.md §3.5 additionally
requires its client be generated, not hand-written, same as the frontend's.
Four decisions were needed to turn `config.example.yaml`'s already-detailed
`simulator`/`scenarios` blocks into a running thing.

## Decisions

### 1. The simulator gets its own config loader, not `dinner_rush_core`

`packages/dinner_rush_core` contains no domain logic, but it does depend on
`redis` and `pyjwt` that the simulator has no use for, and importing it would
mean a config model shaped by services' needs, not the simulator's. Instead
`simulator/config.py` duplicates the ~15 lines of `CONFIG_PATH`
env-var-or-walk-up-from-cwd logic from `dinner_rush_core.config` and models
only `simulator` and `scenarios` — every other top-level key is silently
dropped by `extra="ignore"`. That duplication is the price of the isolation
being real: a reviewer can grep `services/simulator/` for
`dinner_rush_core` or `gateway`/`kitchen` imports and find none, rather than
taking CLAUDE.md's word for it.

Gateway's own config model (`dinner_rush_core.config.RootConfig`) grows
exactly one new field for this — `simulator.customers.population`, which
`manage.py seed` needs to create that many synthetic customers. It's the one
piece of the simulator's config gateway has a legitimate reason to read, and
it's a single int, not a shared model of the simulator's world.

### 2. Poisson arrivals via inverse-CDF sampling, not a fixed-interval loop with jitter

PHASES.md is explicit that an evaluator will check for a fixed-interval loop
wearing a Poisson costume. `simulator/arrivals.py` draws each interarrival
time as `-ln(1 - U) / rate` for `U ~ Uniform[0, 1)` — the standard inverse
transform construction for an Exponential distribution, which is what
governs interarrival times in a Poisson process. `rate_per_minute` is a
callable re-read on every draw rather than captured once, so a scenario
changing it mid-run (`friday_rush`) takes effect on the very next arrival
instead of requiring a restart.

### 3. Cancellation is cart abandonment, not an API call

`config.example.yaml`'s `cancel_probability` has no corresponding endpoint —
SPEC.md's order API has no `DELETE`/cancel action at all. The project's own
rule ("if you find yourself wanting to bypass the API to make the simulator
work, the API is wrong — fix the API") argues the other direction here:
there's nothing to fix, because a customer changing their mind before ever
placing an order needs no API at all. `session.py` rolls the cancellation
check *after* think time and *before* `POST /orders` — an abandoned cart,
counted in `Stats.abandoned`, is simply an order that was never sent.

### 4. Only `friday_rush` is runnable by the simulator this phase

All five chaos scenarios are fully specified in `config.example.yaml`, but
they fall into three groups that don't belong to the same phase:

| Scenario | Mechanism | Runnable by the simulator now? |
| --- | --- | --- |
| `friday_rush` | `overrides` on `simulator.customers.*` | **Yes** — this is the only scenario `make rush` needs to satisfy PHASES.md Phase 6's "done means" |
| `courier_offline` | `overrides` on `simulator.couriers.*` | No — the simulator has no courier behaviour to override yet; dispatch doesn't exist until Phase 7 |
| `oven_down`, `ingredient_shortage` | `actions` — admin API calls (`POST /admin/ovens/{id}/status`, `POST /admin/menu/{sku}/availability`) | No — these are chaos-button features PHASES.md assigns to Phase 10, triggered through a `POST /admin/scenarios/{name}/start` endpoint gateway doesn't implement yet |
| `dispatch_down` | `manual` (`docker compose stop dispatch`) | No — not simulator-driven at all, ever |

`simulator/config.py`'s `apply_scenario_overrides` checks an explicit
allowlist (`_SUPPORTED_SCENARIOS = {"friday_rush"}`) rather than inferring
support from "has `overrides`" alone — `courier_offline` has `overrides` too,
but they target `simulator.couriers.*`, a section this phase's simulator
doesn't read. Silently accepting the override and doing nothing with it
would be worse than refusing clearly: `apply_scenario_overrides` raises
`UnsupportedScenarioError` naming the real reason (needs dispatch / needs
gateway's admin scenario endpoint) rather than a generic "not implemented."

### 5. The generated client follows `apps/web`'s split, not a monolithic codegen

SPEC.md §3.5 requires the simulator's client be generated. Rather than a
full generated client library (e.g. `openapi-python-client`, which produces
its own distributable package with its own build system), `models.py` is
generated by `datamodel-code-generator` from `services/gateway/openapi.json`
— shapes only — and `client/api.py` is a thin, hand-written, endpoint-generic
call layer, exactly mirroring `apps/web`'s `openapi-typescript` (generated
types) + `openapi-fetch` (a thin, generic, hand-written layer). The part that
can drift (request/response shapes) is generated and diff-checked in
`make lint`/CI; the part that's hand-written has no endpoint-specific
knowledge to drift.

## Consequences

- Phase 7 (dispatch) adds `simulator.couriers.*` config modeling and courier
  session behaviour, at which point `courier_offline` moves from
  `UnsupportedScenarioError` to a real, runnable scenario — no change needed
  to the override-application mechanism itself, only to
  `_SUPPORTED_SCENARIOS` and a new courier session module.
- Phase 10 (chaos, recorded) needs gateway's `POST /admin/scenarios/{name}/start`
  to apply `oven_down`/`ingredient_shortage`'s `actions`. That endpoint is
  gateway's responsibility, not the simulator's — the simulator only ever
  patches its own config.
- `manage.py seed`'s synthetic customers (`sim0001@example.com`..) and the
  simulator's `customer_email()` must keep agreeing on the exact format
  without ever importing from each other; a comment on each side names the
  other as the reason it can't change unilaterally.

## Alternatives considered

**Generate a full Python client package (`openapi-python-client`) instead of
models + a thin layer.** Rejected — it produces its own poetry-based
sub-project with generated boilerplate around every operation, which is a
second packaging system to maintain inside `services/simulator/` for no
benefit `openapi-fetch`'s approach doesn't already provide for the frontend.
Consistency with the frontend's split was worth more than "the client is
100% generated."

**Let `apply_scenario_overrides` accept any scenario with an `overrides` key,
including `courier_offline`.** Rejected — it would silently apply an
override to a config section (`simulator.couriers`) nothing reads, which
looks like the scenario ran when nothing observable happened. An explicit
`UnsupportedScenarioError` with the real reason is more honest than a silent
no-op.
