# 0001 — Why three services

## Status

Accepted.

## Context

Dinner Rush could be built as a single Django monolith end to end — the CRUD
surface (menu, customers, orders, pricing, auth) is worthless as a
differentiator either way. The decision that matters is whether to split out
`kitchen` and `dispatch`, and the bar for doing so is high: a service split
that exists only to look like microservices is a worse portfolio piece than
an honest monolith, because it invites "why is this three repos" without a
defensible answer.

The test applied: a service earns its extraction only if it does a
*genuinely different kind of work* from the gateway — different data
structures, different concurrency shape, different failure mode — not because
splitting is fashionable.

## Decision

Three services, split by the shape of the work rather than by team boundary
or deploy cadence (there is one deployer and no team):

| Service | Stack | The work | Why it can't live in the gateway |
| --- | --- | --- | --- |
| `gateway` | Django + DRF + Channels | Menu, customers, orders, staff, pricing, auth, admin, websocket fanout | — it's the CRUD/orchestration home |
| `kitchen` | FastAPI + Celery | Constrained-resource scheduling: finite oven slots, per-item cook times, station contention, a tick loop | It holds genuinely contended state under `FOR UPDATE SKIP LOCKED` and runs a scheduling loop — that's a different runtime shape than request/response CRUD, not a bigger version of it (DECISIONS.md §0002) |
| `dispatch` | FastAPI + Redis GEO | Geospatial assignment: nearest available courier, trip batching, ETA/re-ETA | Different data structure (Redis GEO, not relational rows), different read pattern (proximity queries), different scaling profile |
| `simulator` | plain Python, no DB | Poisson order arrivals, courier movement, chaos injection | It is a client of the public API, not a component of the system. If it could reach a database directly the whole backpressure story would be unfalsifiable — see CLAUDE.md §5 |

`kitchen` is the one that matters. Oven slots are a real contended resource —
two orders racing for the last slot is an actual distributed-systems problem
with a correctness argument and a test, not a contrived one. That's reason
enough on its own to give it a service boundary rather than a Django app.

`dispatch` earns its split on data-structure grounds: courier proximity is a
GEO query, not a SQL join, and pretending otherwise inside the gateway would
mean bolting Redis GEO logic into a request/response app that has no other
reason to hold geospatial state.

## Consequences

- Each service owns its own Postgres database (CLAUDE.md §3) — no shared
  schemas, no shared connection strings. `kitchen`'s database in particular
  never contains customer PII: absent, not filtered.
- Cross-service calls need real boundaries: timeouts, retries, circuit
  breakers, generated clients (Phase 5) — that cost is paid deliberately,
  not accidentally.
- The extractions in Phases 4 and 7 are built as *real refactor commits* out
  of the Phase 2 monolith, not new directories appearing fully formed, so the
  git history shows the decision being made rather than assumed from day one.
- Two web frameworks (Django for `gateway`, FastAPI for `kitchen` and
  `dispatch`) is a real cost — Django because DRF, Channels and the admin
  give the CRUD half for free; FastAPI because the scheduling and geospatial
  services need none of that and benefit from being small and async-native.

## Alternatives considered

**Single Django monolith, no extraction.** Rejected as the primary path
because it forfeits the one thing that makes this project not a CRUD demo:
a service boundary around a contended resource with its own failure modes.
Still built first, deliberately — see Phase 2 — because the extractions
should be refactors with history, not a from-scratch split.

**Split by CRUD entity instead of by workload shape** (e.g. an "orders
service" separate from a "menu service"). Rejected — nothing about orders vs.
menu differs in data structure, concurrency, or failure mode; that split
would be organizational theatre with none of the technical justification
`kitchen` and `dispatch` actually have.

**Kubernetes / multiple deployable replicas per service.** Out of scope
entirely — CLAUDE.md is explicit that this runs on `docker compose` on a
laptop and will never be hosted. Horizontal scaling work here would prove
nothing about the domain and cost real time.
