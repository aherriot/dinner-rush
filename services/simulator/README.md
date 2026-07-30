# simulator

An ordinary API client — its own container, its own dependency file, no
service or database credentials, no imports from `services/front_of_house` or
`services/kitchen`. See CLAUDE.md §5 and [ADR 0006](../../docs/adr/0006-simulator.md).

It authenticates via `POST /auth/token` with a seeded customer email, same as
any real client, and generates Poisson-arrival order traffic against
front-of-house's public API. Courier behaviour lands in Phase 7, once dispatch
exists to call.

## Running it

```
make sim    # baseline rate, indefinitely — Ctrl-C or `docker compose stop`
make rush   # the friday_rush scenario, for its duration_seconds, then stops
```

Both require the stack to be up and seeded (`make up && make seed`) — the
simulator needs `sim0001@example.com`..`sim{population}@example.com` to
already exist, which `manage.py seed` creates from
`config.yaml`'s `simulator.customers.population`.

`--scenario NAME` only runs scenarios whose `overrides` target something this
phase's simulator actually simulates — today, only `friday_rush`. Anything
else (`oven_down`, `ingredient_shortage`, `courier_offline`, `dispatch_down`)
exits with an error naming why (needs front-of-house's admin scenario endpoint,
Phase 10, or dispatch, Phase 7) — see `simulator/config.py`.

## Structure

```
src/simulator/
├── client/          # models.py is generated from front-of-house's openapi.json
│                     (scripts/generate_client.py); api.py is a thin,
│                     hand-written, endpoint-generic call layer on top —
│                     the same split as apps/web's openapi-typescript +
│                     openapi-fetch.
├── config.py        # own YAML loader — reads only `simulator`/`scenarios`
├── arrivals.py       # Poisson process
├── session.py        # one simulated customer's ordering session
├── speed.py           # polls GET /speed so domain-time sleeps scale correctly
├── stats.py           # running counters + periodic terminal summary
├── runner.py          # wires the above into one running simulation
└── cli.py             # `python -m simulator.cli [--scenario NAME]`
```
