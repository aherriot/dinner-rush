# Dinner Rush — build phases

Companion to [PIZZA.md](PIZZA.md). Twelve phases, each with a **done means** you
can demo and a **what this buys you in an interview** line. Phases 0–7 are the
project. 8–11 are what make it a portfolio piece rather than a repo.

**Locked decisions:** React + TS + Vite for the frontend, tokens as a single
generated source. Two UI surfaces — the ops board and a customer
storefront/tracker. Kitchen display and courier view are panels inside the
board, not separate apps.

**Naming.** The project is **Dinner Rush** — repo `dinner-rush`, Python
namespace `dinner_rush`, services `gateway` · `kitchen` · `dispatch` ·
`simulator`. The name does a job: it puts the system under load in front of the
pizza, because the domain is the weak part and the load behaviour is the whole
pitch. Corollary for every piece of copy in the repo — the README, the board
header, the ADRs — **never the phrase "food delivery app."**

---

## Phase 0 — Rails

> Repo layout, stack versions, standing rules and the command surface are in
> [CLAUDE.md](../CLAUDE.md) §3–6. Start there.

Repo layout, `compose.yaml`, one command that works from a clean clone.
Postgres, Redis, gateway skeleton, healthchecks with real readiness. `make up`,
`make demo`, `make test`. Ruff + mypy (strict) + pytest. GitHub Actions running
lint, types and tests. `docs/adr/0001-why-three-services.md` — start the ADR log
now, backfilling it later is obvious.

**Done means:** clone → `make up` → every container healthy in under 90 seconds.

**Buys you:** the first thing anyone does is clone and run. If `docker compose
up` fails on their machine you have already lost, and no amount of architecture
recovers it. This phase is also where you decide the repo is legible — a
reviewer forms an opinion from the directory listing before reading any code.

---

## Phase 1 — Design vision and the design system

**Do this before any screen exists.** Retrofitting tokens onto built UI is how
design systems die; there must never be a component that predates the system.
No backend needed — this phase is pure frontend and can be done in parallel with
nothing blocking it.

> **The authoritative values are in [DESIGN.md](DESIGN.md)** — palette with
> verified contrast ratios, type scale, spacing, the per-state encoding table,
> the component inventory, and the lint configuration. This phase implements
> that document; it does not re-derive it.

**The direction, written down first.** One page in `docs/design/direction.md`
arguing for a specific look, because "clean and modern" is not a direction. The
argument that fits this domain: **this is an operations console, not a consumer
app.** Air traffic control, trading terminal, mission control. Dense over airy.
Dark by default because it's a wall display in a kitchen. Tabular monospace
numerals so digits don't jitter as they tick. Status colour as the primary
information channel, not decoration. Motion only where it carries meaning — a
slot filling, a queue growing — never as flourish. Write down what you are
*rejecting* too: no rounded-friendly SaaS look, no illustration, no gradients.

**The token pipeline.**

```
src/design/tokens.json      ← the only place a value is authored
      ↓ build step
tokens.css (custom props) + tokens.ts (typed) + Storybook theme
```

Two layers, and the distinction matters: **primitives** (`--blue-500`,
`--space-4`) are never referenced by a component. Components may only use
**semantic** tokens (`--color-status-baking`, `--space-panel-gutter`). This is
what makes a re-theme a one-file change and it's the thing most people get
wrong.

**Domain tokens — the part that makes this yours.** A generic button library is
not interesting. Encode the order lifecycle *once*: every state in the FSM gets
exactly one colour, one icon, one label, one text treatment, defined in the
token file and used identically in the feed, the kitchen panel, the map and the
customer tracker. `rejected` is visually distinct from `failed` everywhere,
forever, because there is one definition. Same for oven states and courier
states.

**Identity is part of the system, not an afterthought.** The Dinner Rush
wordmark, the favicon and the board header are tokens like anything else —
defined once, specified in Storybook, and never redrawn per surface. A demo
screen with a hand-placed logo in the corner reads as unfinished in exactly the
frame where polish is being judged.

**Headless UI over hand-built interaction logic.** `Button`, `Modal`, `Select`
and the interactive pieces of `Toolbar` are thin, token-styled wrappers around
`@headlessui/react` (`Button`, `Dialog`, `Listbox`, `RadioGroup`, `Menu`), not
components built from scratch — see DESIGN.md §7 for the full mapping. That
buys focus management, keyboard navigation and ARIA state for free and keeps
this phase's actual custom-code surface to the pieces Headless UI has no
opinion on: `StatusPill`, `Panel`, `Table`, `Meter`, `Sparkline`, `Toast`, plus
the layout grid the board needs. Reach for Headless UI before writing a focus
trap or a roving-tabindex handler by hand — if you're doing either, check
DESIGN.md §7 first.

**Primitives to build:** Button, StatusPill, Panel, Table (dense, virtualised),
Meter, Sparkline, Toolbar, Select, Modal, Toast, plus the layout grid the
board needs. Storybook covering every state including loading, empty, error
and overflow — empty and error states are where portfolio UIs are exposed.

**Enforcement, which is the whole point.**

- stylelint fails CI on any raw hex, `rgb()`, or unitless `px` in component CSS
- ESLint bans inline style colour props
- typed tokens mean an invalid token name is a compile error
- Playwright visual regression snapshots on every Storybook story
- contrast ratios asserted in CI; **status never encoded by colour alone** —
  shape and label carry it too

**Done means:** Storybook builds, every primitive documented in light and dark,
and a PR introducing `color: #3b82f6` fails CI with a readable error.

**Buys you:** most candidates claiming a design system have a colour variables
file. The gap between that and lint-enforced semantic tokens with visual
regression is the entire signal. It is also the only phase where you can
demonstrate taste, and taste is disproportionately memorable.

---

## Phase 2 — The monolith that actually works

Django + DRF. Menu, customers, orders, pricing, auth with the four roles, admin.
Cooking is instant and fake. Storefront and order tracker built from Phase 1
components. Seeded data so the demo has a menu that looks real.

> Entities, FSM transition table, API surface, pricing and the roles matrix are
> specified in [SPEC.md](SPEC.md) §1–3, §5–6. Menu and tunables come from
> [config.example.yaml](../config.example.yaml).

**Timebox this hard.** PIZZA.md is right that the CRUD half is worthless as a
differentiator. The one thing worth doing properly is the **order state machine
as an explicit FSM** — legal transitions declared in one place, illegal
transitions raising, exhaustively tested. It costs a day and every later phase
leans on it.

**Done means:** a human places an order in a browser and watches it reach
`delivered`, all fake, all end to end.

**Buys you:** little on its own. It exists so the extractions later are real
refactors with git history behind them, which is a much better story than
"I started with microservices."

---

## Phase 3 — Time, tasks, and the event spine

Celery with real staged cook times scaled by `SPEED`. The customer tracker goes
live. Then the infrastructure everything else depends on — designed in full in
[DECISIONS.md](DECISIONS.md) 0003 and 0004:

- **Event envelope**: `id`, `type`, `version`, `occurred_at`, `correlation_id`,
  payload. Schemas in the shared package, versioned, validated on publish.
- **Transactional outbox** in the gateway — events written in the same
  transaction as the state change, relayed after commit. No lost events, no
  phantom events.
- **Redis Streams**, not pub/sub. Consumer groups per subscriber.
- **Idempotent consumers**, keyed on event id, with the test that proves
  redelivery is a no-op.
- **Websocket fanout** that resumes from a last-seen event id on reconnect.

**Done means:** kill a consumer mid-stream, restart it, watch it catch up
exactly once. Refresh the browser mid-order and the tracker resumes correctly.

**Buys you:** this is where the "distributed systems" claim is actually earned.
Outbox, idempotency and replay is the trio that separates people who have run
event-driven systems from people who have read about them.

---

## Phase 4 — Extract `kitchen` (the centrepiece)

FastAPI + Celery. Oven slots, per-item cook times, station contention, tick
loop, queue depth, wait-time projection.

**Get the allocation right** — full design in [DECISIONS.md](DECISIONS.md) 0002.
Postgres is the authority; slot rows are claimed under `FOR UPDATE SKIP LOCKED`
with a partial unique index as a second line of defence, and there is no lease
to expire. Redis caches for fast reads and never decides. Then the test that
matters: N
concurrent claims on the last slot, assert exactly one winner, assert zero
overbooking, run it a thousand times in CI. Keep the naive `SET NX EX` version
on a branch with the test that breaks it — being able to show the failure mode
you avoided is worth more than the fix.

**Backpressure in the domain.** `rejected` when projected wait exceeds the
promise. Rejection is a first-class, well-designed response, not an error page.

Kitchen display lands as a board panel using Phase 1 primitives.

**Done means:** load the kitchen past capacity and watch it refuse orders at the
door while continuing to cook cleanly. Concurrency test green.

**Buys you:** the most scrutinised code in the project, and rightly. Contended
resource allocation with a correctness argument and a test that would catch the
regression is a genuine senior signal, and it is the thing that makes this not
an Uber Eats clone.

---

## Phase 5 — Boundaries done properly

Service-to-service auth: gateway signs JWTs, services verify against a published
key. OpenAPI generated from both services; typed clients generated for the
frontend and the simulator (never hand-written — drift is the point). Contract
tests in CI. Every cross-service call gets an explicit timeout, bounded retry
with jitter, and a circuit breaker. Write down what each service does when each
dependency is unavailable, then make the code match.

**Done means:** a generated-client diff appears in a PR when an endpoint
changes; a dependency hanging degrades instead of cascading.

**Buys you:** the difference between "I split it into services" and "I own the
failure modes of the split." Most candidates cannot answer what happens when
service B is slow rather than down.

---

## Phase 6 — Simulator v1

Its own container. **No database credentials, no shared domain imports, its own
dependency file, network-restricted to public API ports.** Enforce the premise
structurally so it's verifiable rather than promised — a reviewer should be able
to confirm it from `docker-compose.yml` alone.

Poisson arrivals, not a fixed-interval loop. Think times, menu preferences,
cancellations. Scenarios as YAML — all parameters and all five chaos scenarios
are already specified in [config.example.yaml](../config.example.yaml).

**Done means:** `make rush` produces genuine concurrent load through the public
API and the kitchen visibly strains.

**Buys you:** this is the phase that pays off Phase 0's premise. It also
converts every later performance claim from an assertion into a reproducible
measurement, which is the difference between a portfolio and a résumé.

---

## Phase 7 — Extract `dispatch`

FastAPI + Redis GEO. Nearest available courier, trip batching, ETA and re-ETA on
disruption. Courier view as a board panel. **Time-boxed address access** —
granted at assignment, revoked at delivery, expiring independently — with the
test that proves a courier cannot read an address before assignment or after
completion.

Map is a stylised city grid in SVG/Canvas. No tile server, no network
dependency, and it suits the console aesthetic better than a real map would.

**Done means:** couriers move, trips assign, and the permission test passes in
all four temporal cases.

**Buys you:** the permission rule is the sharpest security thinking available in
this domain, and time-boxed authorisation is a question people actually get
asked in system design interviews.

---

## Phase 8 — The Board

The four-panel screen. Live over websockets, speed control, chaos buttons.

Treat it as a product, not a debug view. It is the README's first image and it
will receive more attention than every backend decision combined. This is where
Phase 1 pays for itself: dense tables that stay readable at 40 orders/minute,
numbers that don't jitter, transitions that carry meaning, and a layout that
survives a projector and a laptop.

**Done means:** the 45-second story from PIZZA.md plays start to finish without
narration.

**Buys you:** the thumbnail. Unfair as it is, this screen determines whether
anyone reads the rest.

---

## Phase 9 — Observability and proof

OpenTelemetry traces spanning gateway → kitchen → dispatch, correlation id
threaded through the event envelope from Phase 3. Prometheus metrics, a Grafana
dashboard in compose. A k6 or Locust run that emits the real number, checked in
as output, quoted in the README with the command to reproduce it. p50/p95
promise accuracy computed from data rather than asserted.

**Done means:** one order's full journey visible as a single trace waterfall,
and a load-test artifact in the repo.

**Buys you:** a screenshot of a distributed trace crossing three services is
worth more than a page of architecture prose, and it retroactively proves every
claim made earlier.

---

## Phase 10 — Chaos, recorded

All five scenarios one-click. The one that matters: `docker compose stop
dispatch`, keep taking and cooking orders, bring it back, watch the backlog
drain — which only works because Phase 3 chose Streams. Record the GIF.

**Done means:** the degraded-mode recording exists and is honest.

**Buys you:** the answer to "why is this three services." Everything else is
argument; this is evidence.

---

## Phase 11 — The interview surface

README leading with the rush GIF and a claim-plus-evidence structure, never the
words "food delivery app." Architecture diagram. The ADR set, including the
decisions you'd reverse. A `docs/tradeoffs.md` covering what you'd do
differently and what you deliberately didn't build. Clean-clone timing verified.

**Buys you:** a written record of judgement, which is the thing being assessed
and the thing least visible in code.

---

## Off-ramps

PIZZA.md says stopping after the simulator still leaves a real project. Sharper
version: **Phase 6 is the first honest stopping point, and Phase 10 is the
second.** Stopping at 6 gives you contention, backpressure and real load —
already a strong story. Stopping at 10 gives you the whole pitch. Stopping at 7,
with dispatch built but no chaos demo and no measurement, is the worst place to
run out of time, because you'll have paid the full cost of the service split
without any of the evidence that justifies it.

## Explicitly not building

Payments. Email/SMS. A real auth provider. Kubernetes. A service mesh. gRPC. A
virtual clock. Real map tiles. Each is a week that proves nothing here.
