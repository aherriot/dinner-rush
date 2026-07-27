# Dinner Rush

A simulated pizza operation. Orders arrive, a capacity-constrained kitchen cooks
them, couriers deliver them — running as a live simulation you can watch and
break.

**This is a portfolio project.** It is optimised for being run locally from
`docker compose` and demoed on a laptop. It will never be hosted. Decisions
should be made accordingly: no Kubernetes, no cloud services, no horizontal
scaling work, nothing that cannot be shown on one screen in 45 seconds.

---

## 1. Read these first

| Document | Contains |
| --- | --- |
| [docs/PIZZA.md](docs/PIZZA.md) | The original brief and the pitch. Read for intent |
| [docs/PHASES.md](docs/PHASES.md) | Twelve build phases with acceptance criteria |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Slot allocation, event streams, outbox — specified to the SQL |
| [docs/SPEC.md](docs/SPEC.md) | Domain model, FSM, API surface, events, permissions |
| [docs/DESIGN.md](docs/DESIGN.md) | Design tokens with verified contrast, components, enforcement |
| [config.example.yaml](config.example.yaml) | Every tunable and the chaos scenarios |

**Build in phase order.** Phases exist because later ones depend on
infrastructure earlier ones establish — in particular, the event spine (Phase 3)
must exist before the first service extraction (Phase 4), or the outbox and
idempotency get retrofitted into three services instead of built once in one.

---

## 2. What this project is actually about

The CRUD half — menu, orders, customers — is **worthless as a differentiator**.
An evaluator has seen twenty of these. Three things carry the entire project:

1. **Oven slot contention.** A genuinely contended resource with a correctness
   argument and a test that would catch the regression
2. **Backpressure.** The kitchen refuses orders it cannot cook, and `rejected`
   is a designed, first-class response rather than an error
3. **Graceful degradation.** Kill dispatch, keep cooking, recover, drain

When trading off effort, spend it there. Timebox everything else hard.

**Never use the phrase "food delivery app"** — not in the README, not in code
comments, not in UI copy, not in commit messages. The domain is the weakest part
of the pitch; the load behaviour is the pitch.

---

## 3. Repo layout

```
dinner-rush/
├── compose.yaml
├── Makefile
├── config.example.yaml
├── packages/
│   └── dinner_rush_core/        # shared, installed by all Python services
│       ├── events/              # envelope, schemas, catalogue (SPEC.md §4)
│       ├── streams/             # publish, consume, XAUTOCLAIM recovery
│       ├── outbox/              # relay (DECISIONS.md §0004)
│       ├── auth/                # JWT verify, JWKS client, scopes
│       └── config/              # config.yaml loader, SPEED handling
├── services/
│   ├── gateway/                 # Django 5 + DRF        :8000
│   ├── kitchen/                 # FastAPI + Celery      :8001
│   ├── dispatch/                # FastAPI               :8002
│   └── simulator/               # standalone client     (no ports exposed)
├── apps/
│   └── web/                     # React + TS + Vite     :5173
│       └── src/design/          # tokens.json → tokens.css + tokens.ts
├── docs/
│   ├── adr/                     # 0001-… decision records
│   └── design/direction.md
└── scripts/
```

Each service owns **its own Postgres database**. They do not share schemas,
models, or connection strings. `dinner_rush_core` is the only shared code and it
contains no domain logic — envelopes, transport, auth, config, nothing else.

---

## 4. Stack

| | |
| --- | --- |
| Python | 3.12+ |
| Gateway | Django 5.x, DRF 3.15+, Channels (websockets) |
| Kitchen | FastAPI, Celery 5.x, SQLAlchemy 2.x |
| Dispatch | FastAPI, SQLAlchemy 2.x, redis-py |
| Data | Postgres 16, Redis 7.4 (streams, GEO, cache, Celery broker) |
| Frontend | Node 22, React 19, TypeScript 5.x, Vite, Headless UI, Storybook, Playwright |
| Tooling | uv, ruff, mypy (strict), pytest, pnpm, stylelint, eslint |
| Observability | OpenTelemetry, Prometheus, Grafana |

Resolve and pin exact versions in Phase 0, then commit the lockfiles. The above
are floors, not guarantees — verify current releases rather than trusting these
numbers.

---

## 5. Standing rules

Violating any of these is a defect regardless of whether tests pass.

**Architecture**

- **Postgres is authoritative for oven slots.** Redis is a read cache and never
  decides. No `SET NX EX` allocation, no leases. See DECISIONS.md §0002
- **Redis Streams, never pub/sub**, for domain events. Pub/sub has no backlog,
  and a drainable backlog is the entire recovery demo
- **Every state change writes its event in the same transaction** via the outbox
- **Every consumer is idempotent by `event_id`**, deduped in the same
  transaction as its side effect
- Kitchen and dispatch **never** receive a gateway database connection string
- Kitchen's database contains **no customer PII**. Not filtered — absent

**The simulator**

- It is an ordinary API client. It authenticates via `POST /auth/token`, holds
  no service or database credentials, and imports nothing from `services/`
- Enforced in `compose.yaml`: no DB env vars, no privileged scope. If you find
  yourself wanting to bypass the API to make the simulator work, the API is
  wrong — fix the API

**Time**

- **No virtual clock.** Everything runs on wall time
- Durations are stored in domain seconds and divided by `SPEED` **at the point
  of use**. Never store pre-scaled values. SPEC.md §5

**Frontend**

- No component authors a colour, spacing value, radius or duration. Semantic
  tokens only; primitive tokens never leave `tokens.json`. DESIGN.md §9
- A component file containing `#`, `rgb(`, `hsl(` or a raw px in a colour or
  spacing property is a defect
- Status is never encoded by colour alone — glyph and label carry it too
- `rejected` is violet, not red. It is correct behaviour, not an error
- **Interactive primitives are built on Headless UI, not from scratch.**
  Dialog, Menu, Listbox/Combobox, RadioGroup, Switch, Tabs, Disclosure and
  Popover supply focus management, keyboard navigation and ARIA wiring;
  our code only skins them with semantic tokens via `data-*` state
  selectors. Writing a bespoke focus trap or roving-tabindex handler is a
  defect if Headless UI already ships the interaction — see DESIGN.md §7
  for the component-by-component mapping. This does not extend to
  domain-specific visualisation (`StatusPill`, `Panel`, `DataTable`,
  `Meter`, `Sparkline`, `OvenSlot`, `CourierDot`) or `Toast`, none of which
  Headless UI covers — those stay hand-built

**API**

- Rejection at capacity is a **successful response** with `status: rejected`,
  not a 4xx and not a 503
- API clients are generated from OpenAPI, never hand-written
- Errors are RFC 7807 `application/problem+json` with a `correlation_id`

---

## 6. Commands

```bash
make up            # bring the stack up; every container healthy in <90s
make down
make seed          # menu, customers, couriers, ovens from config.yaml
make demo          # up + seed + open the board — the one-command entry point
make sim           # start the simulator at baseline rate
make rush          # trigger the friday_rush scenario
make test          # all Python tests
make test-fe       # vitest + Playwright visual regression
make lint          # ruff, mypy, stylelint, eslint, token build check
make storybook
make load          # k6 run; writes docs/load/latest.json
```

`make demo` from a clean clone must work first try. It is the first thing anyone
does and no amount of architecture recovers from it failing.

---

## 7. Conventions

**Python** — ruff (line length 100), mypy strict on `packages/` and
`services/*/src`. Pydantic v2 for all boundaries: API bodies, event payloads,
config. No bare `dict` crossing a service boundary.

**Tests** — pytest, `tests/` beside each service. Name tests for the behaviour,
not the function (`test_last_slot_has_exactly_one_winner`, not
`test_claim_slot`). Concurrency tests use real Postgres via testcontainers or
the compose DB — never mocked. The contention test runs with `pytest-repeat` in
CI.

**Commits** — conventional commits. **The service extractions in Phases 4 and 7
must be real refactor commits**, not new directories appearing fully formed. The
git history is part of the portfolio: it shows a monolith becoming a distributed
system deliberately, which is a much better story than starting with
microservices.

**ADRs** — `docs/adr/NNNN-title.md`. One per non-obvious decision, written when
the decision is made rather than reconstructed later. At minimum: why three
services, why Postgres owns slots, why Streams over Kafka, why no virtual clock,
why mixed Django/FastAPI.

**Frontend** — components colocate `Component.tsx`, `Component.module.css`,
`Component.stories.tsx`, `Component.test.tsx`. Every component gets loading,
empty and error stories; those states are where portfolio UIs get exposed.

---

## 8. Definition of done, per phase

A phase is complete when: its acceptance criterion in PHASES.md demonstrably
passes, `make lint` and `make test` are green, new decisions have ADRs, and any
new UI has Storybook stories including empty/loading/error.

Do not begin a phase before the previous one meets that bar. The failure mode
for this project is a broad, shallow build that demos badly — the value is
concentrated in a few things done properly.

---

## 9. Known-weak areas to watch

- **The domain is a cliché.** Compensate with the contention test, the
  backpressure numbers and the degraded-mode recording. Lead with those
- **Two web frameworks** need one honest sentence of justification in the
  README, not a paragraph of rationalisation
- **The board is the thumbnail.** It will receive more attention than every
  backend decision combined. Budget accordingly; it is Phase 8 and it is not
  polish
- **Claims need artifacts.** "40 orders/minute" is only allowed in the README if
  `docs/load/latest.json` produces it and the command to reproduce is printed
  next to it
