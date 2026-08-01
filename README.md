# Dinner Rush

A simulated pizza kitchen running under real, generated load — orders arrive,
a capacity-constrained kitchen cooks them, couriers deliver them, and the
whole thing runs live on one screen you can watch and break.

The domain is a cliché on purpose. What isn't: a genuinely contended oven
resource with a correctness argument and a 200-repeat concurrency test, a
kitchen that refuses orders it cannot cook instead of silently degrading, and
a dispatch service you can kill mid-demo while the rest of the system keeps
working and drains the backlog on recovery. See
[docs/PIZZA.md](docs/PIZZA.md) for the full pitch.

**Status: Phases 0–9 built** (rails → design system → monolith → event spine
→ kitchen extraction → service boundaries → simulator → dispatch extraction →
the live board → observability). Chaos recording (Phase 10) and the
architecture write-up (Phase 11) are next. See
[docs/PHASES.md](docs/PHASES.md) for what each phase means and why it's
ordered this way.

## Quickstart

```bash
make demo    # up + seed + prints the URL — the one-command entry point
make ui      # cd apps/web && pnpm run dev
```

Open `http://localhost:5173/board` and sign in as `manager` / `manager` (or
`kitchen` / `kitchen` for the kitchen-only view). Then generate load:

```bash
make sim     # baseline order rate, runs until Ctrl-C
make rush    # the friday_rush chaos scenario
```

or stop `dispatch` mid-demo (`docker compose stop dispatch`) and watch orders
keep cooking while deliveries queue, then bring it back and watch the backlog
drain.

```bash
make lint    # ruff, mypy strict, stylelint, eslint, token + generated-client drift
make test    # all Python tests against real Postgres + Redis
make test-fe # vitest + Storybook interaction/a11y + Playwright visual regression
make load    # k6 run against a live stack; writes docs/load/latest.json
```

## Architecture

```
simulator ──HTTP──► front-of-house (Django + DRF) :8000
                            │  every state change writes its event
                            │  in the same transaction, relayed via
                            │  an outbox onto Redis Streams
                            ▼
                     kitchen (FastAPI + Celery) :8001
                       oven slots claimed with Postgres
                       FOR UPDATE SKIP LOCKED — no locks, no leases
                            │
                            ▼
                     dispatch (FastAPI) :8002
                       nearest-courier via Redis GEO,
                       time-boxed address grants
```

Each service owns its own Postgres database — no shared schema, no shared
connection strings. Kitchen's database contains no customer PII: absent, not
filtered. The simulator is an ordinary API client with no database
credentials and no imports from `services/` — enforced structurally in
`compose.yaml`, not just promised. See
[CLAUDE.md §3](CLAUDE.md#3-repo-layout) for the full layout and
[docs/adr](docs/adr) for why it's split this way, including
[why three services](docs/adr/0001-why-three-services.md).

**Why two web frameworks.** Front-of-house is CRUD-and-admin-heavy — Django's
batteries (auth, admin, ORM migrations) are the right fit. Kitchen and
dispatch are small, high-throughput, I/O-bound services with no admin
surface, where FastAPI's async story and lighter footprint fit better. The
split follows the shape of the work, not a resume checklist.

## The load-bearing pieces

- **Oven slot allocation** — [docs/DECISIONS.md §0002](docs/DECISIONS.md).
  Postgres is authoritative; the claim is a single `UPDATE ... FOR UPDATE
  SKIP LOCKED` with a partial unique index as a second line of defence. No
  Redis lock, no lease to expire. `services/kitchen/tests/test_slots.py`
  runs 200 concurrent claims on the last slot in CI, asserts exactly one
  winner. The rejected `SET NX EX` lease design lives on
  `spike/redis-lease-allocation` with the test that shows how it fails.
- **Backpressure** — the kitchen refuses orders it projects it cannot cook by
  the promised time. `status: rejected` is a normal, successful API
  response, not a 4xx or 503.
- **Event spine** — [docs/DECISIONS.md §0003–§0004](docs/DECISIONS.md).
  Redis Streams (never pub/sub — a backlog is the entire recovery story),
  a transactional outbox so no event is ever lost or phantom, and
  idempotent consumers keyed on `event_id` with an out-of-order guard on top.
- **Graceful degradation** — kill `dispatch`, keep cooking, bring it back,
  watch `XAUTOCLAIM` drain the backlog with zero manual replay. See
  [docs/degradation.md](docs/degradation.md) for what every service does
  when every dependency is unavailable.
- **Proof** — [docs/adr/0009-observability.md](docs/adr/0009-observability.md).
  One order's full journey is a single trace waterfall spanning all three
  services (Grafana → Explore → Tempo), `stream_pending` and
  `promise_error_seconds` (SPEC.md §7) are real Prometheus metrics visible on
  both a Grafana dashboard and the board's own status bar, and `make load`
  produces a committed, reproducible throughput/rejection-rate number instead
  of an asserted one. Latest run (`docs/load/latest.json`, `make load` to
  reproduce, `SPEED=60`): **113 orders/min accepted, 57.7% rejected once the
  ramp passes configured capacity** — one 80-second run against a genuinely
  contended kitchen, not two separate claims.

## Decisions

- [0001 — Why three services](docs/adr/0001-why-three-services.md)
- [0002 — Phase 2 front-of-house foundations](docs/adr/0002-phase-2-front-of-house-foundations.md)
- [0003 — The event spine](docs/adr/0003-event-spine.md)
- [0004 — Kitchen extraction and oven slots](docs/adr/0004-kitchen-extraction-and-oven-slots.md)
- [0005 — Service boundaries](docs/adr/0005-service-boundaries.md)
- [0006 — The simulator](docs/adr/0006-simulator.md)
- [0007 — Dispatch extraction and the address grant](docs/adr/0007-dispatch-extraction-and-address-grant.md)
- [0008 — The board](docs/adr/0008-the-board.md)
- [0009 — Observability: one collector, a threaded trace, and a real load number](docs/adr/0009-observability.md)

## Docs

| Document | Contains |
| --- | --- |
| [docs/PIZZA.md](docs/PIZZA.md) | The original brief and the pitch |
| [docs/PHASES.md](docs/PHASES.md) | Twelve build phases with acceptance criteria |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Slot allocation, event streams, outbox — specified to the SQL |
| [docs/SPEC.md](docs/SPEC.md) | Domain model, FSM, API surface, events, permissions, metrics |
| [docs/DESIGN.md](docs/DESIGN.md) | Design tokens with verified contrast, components, enforcement |
| [docs/degradation.md](docs/degradation.md) | What each service does when each dependency is down |
| [config.example.yaml](config.example.yaml) | Every tunable and the five chaos scenarios |

See [apps/web/README.md](apps/web/README.md) for the frontend command surface
and [docs/DESIGN.md](docs/DESIGN.md) for the token system itself.

## Stack

Python 3.12+, Django 5 + DRF (front-of-house), FastAPI + Celery (kitchen),
FastAPI + Redis GEO (dispatch), Postgres 16, Redis 7, React 19 + TypeScript +
Vite (Storybook, Playwright), OpenTelemetry + Prometheus + Grafana. See
[CLAUDE.md §4](CLAUDE.md#4-stack) for exact pinned versions.
