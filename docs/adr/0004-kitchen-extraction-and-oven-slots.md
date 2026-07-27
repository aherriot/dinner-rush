# 0004 — Extracting kitchen: oven-slot allocation and backpressure

## Status

Accepted.

## Context

Phase 4 is the centrepiece (CLAUDE.md §2): a genuinely contended resource
with a correctness argument and a test that would catch the regression, plus
real backpressure — `rejected` as a designed response, not an error. Building
it meant extracting `kitchen` as a real service (FastAPI + SQLAlchemy, its
own Postgres, no gateway connection string) and wiring it into gateway's
order flow without gateway ever touching kitchen's database.

DECISIONS.md §0002 already specifies the slot-claim SQL to the character.
What it doesn't specify is everything the *integration* needed once kitchen
existed alongside a gateway that, until Phase 3, drove the entire FSM by
itself. Four decisions were made getting there.

## Decisions

### 1. Kitchen claims exactly one slot per ticket, regardless of `menu_item.oven_slots`

SPEC.md §1.1 gives `menu_item` an `oven_slots` field ("usually 1; a party
size takes 2"), implying an order can need two slots claimed atomically.
Phase 4 doesn't implement that — every ticket claims one slot, sized by the
slowest item's bake time. Atomic multi-slot claims are a real extension of
the same `SKIP LOCKED` query (claim N rows in one statement instead of one),
not a redesign, but they add nothing to the correctness argument the
contention test already makes with N=50 claimers on one slot. Flagged here
so it doesn't read as an oversight: `PART` (party size, `oven_slots: 2`) is
seeded and priced correctly, it just doesn't reserve two slots yet.

### 2. Gateway's `Order.status` becomes a passive mirror of kitchen's events, not a re-derivation of them

Before kitchen existed, `gateway.orders.tasks` drove `enqueue` through
`mark_ready` itself, so every transition went through `fsm.apply_transition`
directly. Now kitchen drives those transitions and gateway only hears about
the ones with a catalogue event (`order.queued`, `order.baking`,
`order.baked`, `order.ready` — not `start_prep`, which has none). A new
handler, `cg:order-sync`, sets `Order.status` to the value each event type
implies rather than calling `apply_transition(status, event)`: kitchen
already validated the transition before firing the event, and gateway's own
strict single-hop table would reject `start_bake` fired from `queued`
(skipping the unobserved `prepping` step) even though nothing is wrong.
Gateway's mirror of `status` intentionally coarsens `prepping` into
`queued` until the next event arrives — a real, documented simplification,
not a bug to fix later, because there is no event that would let gateway
represent it more precisely without kitchen publishing one it doesn't need
for its own purposes.

### 3. `SPEED` is runtime state, shared over Redis — and kitchen has to read it too

DECISIONS.md and SPEC.md §5 already establish that `POST /admin/speed`
writes to Redis so every service can read the live value instead of
`config.yaml`'s boot-time default. It said "every service that later reads
it (kitchen, dispatch) shares the same Redis" back when only gateway existed
to read it. Phase 4 is where that sentence became a real integration point,
and it was the actual bug caught while verifying this phase manually against
the running stack: kitchen's Celery tasks were reading `config.yaml`'s
static `speed` directly, so a `POST /admin/speed` from the board would speed
up gateway's own remaining fake steps while kitchen kept baking at the
original rate — invisible in any unit test (each service's tests mock or
fix `SPEED` independently) and only visible by actually running the demo.
Fixed by moving the key name and fallback logic into
`dinner_rush_core.speed`, so gateway and kitchen read the identical Redis
key through the identical fallback rather than two independent
almost-identical implementations that could drift.

### 4. `POST /capacity/quote`'s response drops the `promised_at` field SPEC.md's table lists

SPEC.md §3.3's table lists `{can_accept, promised_at, queue_depth,
projected_wait_s}` as the quote response. But §5's formula —
`promised_at = accepted_at + projected_wait_s + drive_estimate_s + buffer_s`
— needs `accepted_at`, which doesn't exist yet at quote time: the quote is
requested *before* gateway decides to accept. Kitchen's quote returns
`{can_accept, queue_depth, projected_wait_s}`; gateway computes
`promised_at` itself from `projected_wait_s`, exactly as §5 already
specifies. `drive_estimate_s` is `0` until Phase 7's dispatch exists to
estimate one — there is nothing to estimate a drive time from without a
courier.

## Consequences

- Phase 7 (dispatch extraction) inherits the same integration pattern as
  Phase 4: dispatch will need its own `cg:order-sync`-style fold-back for
  `courier.assigned`/`order.picked_up`/`order.delivering`, and gateway's
  `orders/tasks.py` (currently the `assign -> deliver` stand-in) shrinks to
  nothing as dispatch takes over those transitions the same way kitchen took
  over `enqueue -> mark_ready`.
- Multi-slot atomic claims for party-size orders are unimplemented; if this
  ever matters for a demo, it's a query change in `kitchen.slots.claim_slot`
  (claim N free rows instead of one), not a schema change.
- `dinner_rush_core.speed` is now the canonical SPEED read for every future
  service — dispatch reads it the same way, from day one, instead of
  discovering the same bug a third time.

## Alternatives considered

**Give kitchen a full copy of gateway's FSM and re-validate every
transition on the gateway side.** Rejected — it would require kitchen to
publish an event for every micro-transition (including `start_prep`, which
the catalogue deliberately has no event for) purely so gateway's stricter
table stays satisfiable, adding event traffic with no consumer that needs
it.

**Have gateway poll kitchen's `/queue` for order status instead of
consuming its events.** Rejected — it would reintroduce exactly the
polling problem Phase 3's websocket fanout replaced, and it can't produce
the timeline history `GET /orders/{code}/timeline` needs; events give both
the current state and the history in the same write.

**Implement atomic multi-slot claims now, since `oven_slots: 2` is already
seeded.** Rejected for this phase on cost/benefit — it doesn't strengthen
the contention test's argument (which needs contention on *a* slot, not
specifically on a multi-slot claim), and the single-slot query already
proven correct 200 times over is the artifact worth having finished instead
of half-extending.
