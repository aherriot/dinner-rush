# 0008 — The board: multi-stream fanout, chaos control, and honest metrics

## Status

Accepted.

## Context

Phase 8 assembles the four-panel board (PIZZA.md's demo, DESIGN.md §10) live
over websockets, with a speed control and chaos buttons. Everything it
displays already exists — orders in gateway, ovens/queue in kitchen, trips/
couriers in dispatch, the event spine from Phase 3 — but nothing had ever
needed to read *all three* services at once, fan out *all three* event
streams to one browser tab, or let a manager change live system behaviour
from a click rather than a CLI flag. Six decisions were made getting there,
plus one deliberate scope line: chaos buttons get real effects for four of
the five scenarios, and `dispatch_down` stays a manual `docker compose stop
dispatch` step, exactly as `config.example.yaml` already specifies it (it
alone carries `manual:`, not `overrides`/`actions`).

## Decisions

### 1. `/ws/board` multiplexes three streams into one fixed group, not three per-purpose sockets

`OrderTrackerConsumer` (Phase 3) joins a per-order group (`order.{id}`) and
replays one stream. The board has no single aggregate to key a group on —
there is one board, watched by however many manager/kitchen tabs are open —
so `BoardConsumer` joins one fixed group, `"board"`, fed by a new handler
(`handle_board_fanout`) that `group_send`s every event regardless of which
of the three streams (`events:order`/`events:oven`/`events:courier`,
DECISIONS.md §0003) produced it. Reaching the group from all three requires
three `stream_consumer` processes sharing one consumer-group name,
`cg:ws-board-fanout` — the same "one process per stream, same group name"
split `cg:order-sync` already uses for `events:order`/`events:courier`
(ADR 0007 §4), just times three.

Resumption follows from the same shape: a client tracking one position
(`?last_event_id=`) becomes a client tracking three
(`?last_event_id_order=`/`_oven=`/`_courier=`), each replayed independently
via `XRANGE` against its own stream with no aggregate filter — the board
wants everything, not one aggregate's history.

### 2. The frontend applies order events directly to state; oven/courier events trigger a debounced re-fetch

`OrderTracker`'s socket treats every push as "go re-fetch the REST shape,"
which is fine for one order's small payload but wrong for a board doing
this on every event of a 40-orders/minute rush. Every `order.*` event's
payload carries enough (`code` plus whatever changed) to move that order's
row to its next status client-side with no round trip — `useBoardSocket`
hands raw envelopes to a pure reducer (`boardState.applyOrderEvent`) keyed
by `event_type`, mirroring gateway's own `handlers.py`
`_EVENT_TYPE_TO_TRANSITION` table so the board and gateway's order-sync
consumer agree on what each event means.

Oven and courier events are different: `oven.slot_freed` carries only
`oven_id`/`slot_index`, not the occupancy grid a redraw needs, and courier
events don't carry position. Rather than growing those payloads just to
satisfy a board redraw, the board treats `events:oven`/`events:courier`
messages as a dirty signal and re-fetches `/board/snapshot` after a 300ms
debounce — cheap in practice, since oven/courier events are far less
frequent than order events, and it avoids a fetch storm if several arrive in
a burst (an oven going down and its four slots freeing, say).

### 3. Chaos scenarios split into two control mechanisms, not one

`config.example.yaml`'s five scenarios turn out to need two genuinely
different kinds of "on": two (`friday_rush`, `courier_offline`) are
parameter *overrides* to a continuously-running process (the simulator);
two (`oven_down`, `ingredient_shortage`) are one-shot *actions* against
existing admin endpoints; the fifth (`dispatch_down`) is `manual:` in config
and was left as a `docker compose` step on purpose, not wired to a button.

**Overrides** get a new Redis-backed mechanism
(`gateway/board/scenario_state.py`) that is deliberately the SPEED precedent
(`accounts/speed.py`) generalised one step: `POST /admin/scenarios/{name}/
start` writes the scenario's `overrides` dict to `scenario:override:<name>`
with `EX duration_seconds` when the scenario has one — a Redis TTL *is* a
wall-clock expiry, so "this scenario ends itself after its configured
duration" needs no scheduler, thread, or Celery beat entry. `GET /scenarios/
active` (public, unauthenticated, same reasoning as `GET /speed`: the
simulator has no service credentials to read Redis directly) merges every
live override key and is what a new `ScenarioOverrideTracker` in the
simulator polls, applying `baseline_rate_per_minute`/`basket_size_weights`
live to the running Poisson arrival loop and basket picker
(`runner.py`/`session.py`) rather than only at `--scenario` CLI-launch time.

**Actions** get no persisted "is it active" flag at all — `oven_down`'s
`at_seconds: 0` action (`POST /admin/ovens/{oven_3}/status` →
`{status: down}`) runs synchronously inside `.../start`, and its
`at_seconds: 300` revert runs inside `.../stop`; same split for
`ingredient_shortage`'s two `/admin/menu/{sku}/availability` calls. This
means neither scenario auto-expires after `duration_seconds` the way the
override scenarios do — the manager's own `.../stop` click is what reverts
them. That is a real, deliberate scope line: auto-expiring the *actions*
scenarios on a wall-clock timer is exactly the kind of scheduler this ADR's
§2 argues Redis TTL avoids for overrides, and building one just for two
scenarios' revert step is Phase 10 territory ("wire all five scenarios...
assert the expectation"), not this phase's.

`courier_offline`'s override (`simulator.couriers.spontaneous_offline_
probability`) is tracked identically to `friday_rush`'s but is never read by
anything — the simulator doesn't simulate couriers at all; dispatch's own
Celery autopilot does (ADR 0007 §6). `ScenarioOverrideTracker` holds the
value but has no method surfacing it, matching `config.
apply_scenario_overrides`'s existing CLI-side refusal to run `courier_
offline` at all, for the same reason. Wiring a probability nothing reads
would be scope theatre, not a scenario.

### 4. `oven_down` gets a real kitchen write endpoint and its own per-aggregate sequence counter

Making the oven-down button real requires kitchen to accept a status write
at all — before this phase it only ever read (`GET /ovens`) or advanced
tickets (`POST /tickets/{id}/advance`). `POST /ovens/{id}/status` (scope
`kitchen:advance`, reached only via gateway's minted service token — a
board calling kitchen directly with a staff token is still the ADR 0005/
kitchen's own `auth.py` gap, unresolved by this phase) flips `Oven.status`
and emits `oven.down`/`oven.restored` (already catalogued, SPEC.md §4) through
kitchen's own outbox in the same transaction.

Every other kitchen event threads its `sequence` through an order's
causation chain (`envelope.sequence + 1`, etc.) because it always has an
upstream event to chain from. An admin-triggered oven flip doesn't — there
is no causing event, and an oven is a long-lived aggregate an admin can flip
repeatedly over a demo's lifetime, unlike an order (fresh aggregate every
time, so `sequence=1` is always correct there). `Oven` gains its own
`event_sequence` column, incremented once per real flip and reused as
`EventEnvelope.sequence` — a small, genuine schema change (migration 0002),
not a workaround.

A repeated call with the status unchanged is a deliberate no-op (no event,
no sequence bump) — clicking "oven down" twice should not manufacture two
`oven.down` events for one real transition.

### 5. The board's own auth is a separate context, not a role added to the customer one

`AuthContext` (Phase 2/3) models one login shape (customer email only) and
is consumed by the storefront and order tracker. Staff login
(`username`+`password`, seeded `manager`/`manager` and `kitchen`/`kitchen`)
already worked server-side (`TokenView`) but had no frontend path at all.
Rather than widening `AuthContext.customer`'s type into a customer-or-staff
union — rippling into every existing consumer for a login shape they never
use — the board gets its own `BoardAuthContext`/`useBoardAuth`, its own
sessionStorage key (`dinner-rush:board-access-token`), and its own login
form. Both ultimately call the same singleton `setAccessToken` (`api/
client.ts`), so there's exactly one bearer token live in a tab at a time —
correct, since nothing in this app is ever simultaneously a customer and a
manager in the same browser tab.

### 6. Board metrics are honestly-labelled approximations, not fabricated Phase 9 numbers

The status bar's "rate" and "p95 late" (PIZZA.md's mockup) have no backing
metric yet — `orders_placed_total`/`promise_error_seconds` (SPEC.md §7) are
Prometheus counters/histograms Phase 9 builds. Rather than wiring nothing
and leaving the numbers blank, or wiring something that *looks* like the
real metric, the board computes both client-side from data it already has:
"rate" is a rolling count of orders seen in the last 60 real seconds;
"p95 late" is the percentage of currently in-flight orders flagged `late`
(SPEC.md §2's derived boolean) — not a percentile of anything, despite the
mockup's label. Both are real, reproducible numbers, not fabricated ones,
and both are commented in `boardState.ts` as approximations of what Phase 9
computes properly, so neither reads as an oversight or an overclaim later.

## Consequences

- Kitchen's oven table now has a schema column (`event_sequence`) whose only
  purpose is a chaos demo button — a small, deliberate exception to
  "schema changes should be domain-driven," recorded here rather than left
  unexplained.
- `oven_down`/`ingredient_shortage` do not self-revert after
  `duration_seconds` the way `friday_rush`/`courier_offline` do; a manager
  (or the eventual Phase 10 scenario runner) must call `.../stop`. Phase 10
  inherits this gap explicitly rather than rediscovering it.
- Two authentication contexts now exist in `apps/web/src/auth/` on purpose —
  a future reviewer should not "simplify" them into one without re-reading
  this ADR's §5.
- The board's rate/late-percentage figures will visibly disagree with
  Phase 9's Prometheus-backed numbers once those exist (different sample
  windows, different definitions of "late") — expected, not a bug to
  reconcile.
