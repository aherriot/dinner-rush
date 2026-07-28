# dispatch

FastAPI + Celery + Redis GEO, port 8002. Courier assignment, a detour-
tolerance trip-batching heuristic, and the time-boxed address grant
(SPEC.md §1.3, §3.4, §6.2). Extracted from the gateway in Phase 7 — see
[PHASES.md](../../docs/PHASES.md) and [ADR 0007](../../docs/adr/0007-dispatch-extraction-and-address-grant.md).

Its own Postgres database (`dispatch`), never gateway's or kitchen's
connection string. Redis holds live courier positions (GEO) only — nothing
about a courier's status or a trip is ever durable anywhere but Postgres.

```
dispatch/
├── main.py           # FastAPI app — courier + trip routers
├── assignment.py     # nearest-idle-courier + batching heuristic, ETA math
├── geo.py            # Redis GEO wrapper, grid <-> lon/lat, Chebyshev distance
├── fsm.py            # trip state machine
├── tasks.py          # Celery: assignment retry + courier motion autopilot
├── consumers.py       # cg:dispatch on events:order (order.placed, order.ready)
├── auth.py           # JWKS-verified service + courier tokens
└── cli.py            # relay / seed / stream_consumer, same shape as kitchen's
```

Run `python -m dispatch.cli seed` (via `make seed`) to create
`dispatch.courier_count` couriers, already `idle` with a starting position
near the restaurant — there's no simulator-driven courier actor yet (ADR
0007 §6), so seeding online is what makes `make demo` assign trips without
any manual setup.
