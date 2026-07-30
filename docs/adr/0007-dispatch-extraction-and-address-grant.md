# 0007 — Extracting dispatch: courier assignment and the time-boxed address grant

## Status

Accepted.

## Context

Phase 7 extracts `dispatch` (FastAPI + Redis GEO), replacing the fixed-delay
`assign -> pick_up -> depart -> deliver` stand-in front-of-house has run since Phase
3 (`front_of_house/orders/tasks.py`). SPEC.md §1.3, §3.4 and §6.2 specify the schema,
API surface and the address-grant rule to the character. What they don't
specify is how a service that must never receive front-of-house's database
connection string gets hold of a delivery address in the first place, given
front-of-house is the *only* JWT signer (SPEC.md §6.3) — kitchen and dispatch can
verify, never call each other or front-of-house synchronously as anything but a
verifier. Five decisions were made getting there.

## Decisions

### 1. `order.placed` carries the dropoff address; dispatch caches it ahead of `order.ready`

Kitchen must never see customer PII, which is why `order.accepted`'s payload
has never carried an address. Dispatch has no such restriction — its own
schema (`address_grant.line1`) already holds address text, just gated from
the *courier* by the time-box, not absent from the *service* the way it is
from kitchen. So `OrderPlacedPayload` gains one additive field, `line1`
(`grid_x`/`grid_y` were already there), and dispatch's own consumer group
(`cg:dispatch`, subscribed to `events:order` like every other group) reacts
to `order.placed` by writing a `pending_dropoff` row — `order_id`, `code`,
`dropoff_x/y`, `line1` — before it ever sees `order.ready` for that order.

This is durable, not an in-memory cache: `docker compose stop dispatch` mid-
flight and the row is still on disk when it restarts, which is the property
the whole three-service split is supposed to buy. It also means kitchen's
event stream is untouched — `order.accepted`'s payload is unchanged, and
kitchen's ticket consumer never receives address data even transiently.

`order.ready`'s own payload stays address-free (SPEC.md's placeholder note in
`schemas.py` reads as dispatch becoming the field's *owner*, not its
producer) — kitchen fills `grid_x`/`grid_y` with the restaurant's fixed pickup
point from `config.yaml`'s `dispatch.restaurant`, which is shared config, not
PII, and identical for every order.

### 2. No trip row until assignment succeeds; `pending_dropoff` is the only pre-assignment state

`trip.status` per SPEC.md §1.3 is `assigned|picked_up|delivering|delivered|
failed` — no "waiting for a courier" state. Rather than inventing one on
`trip`, dispatch attempts assignment synchronously inside the `order.ready`
handler; if `GEOSEARCH` finds no idle courier in range, the attempt reschedules
itself via Celery countdown (`assignment_retry_seconds`), same shape as
kitchen's oven-slot claim retry (`kitchen/tasks.py`'s `CLAIM_RETRY_COUNTDOWN_SECONDS`).
The `pending_dropoff` row is the durable state a crash-and-restart resumes
from; there is deliberately no in-memory queue holding it.

### 3. Trip batching is a detour-tolerance heuristic, not a routing optimizer

`config.yaml` specifies `max_trips_per_courier` and `batch_max_detour_cells`.
Real multi-stop routing (TSP-adjacent) is a research problem, not a weekend
of portfolio work, and CLAUDE.md says spend effort on the three
differentiators, not here. The heuristic: before searching for an idle
courier, check couriers already `assigned`/`delivering` with fewer than
`max_trips_per_courier` active trips, and take the first whose *added*
Chebyshev distance (current route's last leg -> new pickup -> new dropoff,
minus what the direct trip would have cost) is within `batch_max_detour_cells`.
No candidate passes → fall back to nearest idle courier via `GEOSEARCH`. This
is a real, testable rule, just not an optimal one — noted here rather than
overclaimed in the README.

### 4. `unassign` needs an event and a trip status the SPEC table doesn't list

SPEC.md §2's FSM has `assigned --unassign--> ready` and `picked_up
--unassign--> ready` (courier-offline chaos scenario), but §4's event
catalogue has no event for it. Added `order.unassigned` (`events:order`,
producer dispatch, consumers front-of-house/ws) and a `trip.status` value of
`unassigned` — the superseded trip's terminal marker, distinct from `failed`
(which carries a delivery-attempt `failure_reason`; `unassigned` never does).
On courier-offline, dispatch revokes the trip's `address_grant`, marks the
trip `unassigned`, publishes `order.unassigned`, and re-attempts assignment
using the same dropoff data (still on the just-superseded trip row) rather
than needing a second `pending_dropoff` write.

Likewise, `courier.assigned` needed a stream: it's about the *courier*
aggregate (`aggregate_type="courier"`), so it publishes on `events:courier`,
while `order.picked_up`/`order.delivering`/`order.unassigned` are about the
*order* aggregate and stay on `events:order` alongside the already-catalogued
`order.delivered`/`order.failed`. Front-of-house's `cg:order-sync` now runs two
processes — one per stream, same group name, same handler dispatch by
`event_type` — mirroring how `manage.py stream_consumer` already takes
`--group`; it now also takes `--stream`.

### 5. Courier auth is dispatch-verified, front-of-house does not yet issue courier tokens

Kitchen's `auth.py` already flagged this gap: simplejwt's customer/staff
tokens have no `kid` header, so they can't be verified via the JWKS path
kitchen and dispatch both use, and fixing that for every existing role is a
bigger refactor than this phase's actual payoff. Dispatch's `auth.py` mirrors
kitchen's exactly — `role == "service"` with a scope for front-of-house-originated
calls (there are none synchronous in this phase; reserved for future use),
plus a new `role == "courier"` check with `scope=["courier:own"]` and a
`sub == courier_id` match for self-scoped endpoints (`/couriers/me/trips`,
`/trips/{id}/pickup`, etc.). Tests mint RS256 courier tokens directly
(`services/dispatch/tests/test_address_grant.py`), the same way
`test_service_auth.py` does for kitchen — nothing here depends on front-of-house's
`POST /auth/token` actually issuing one yet. Wiring front-of-house to mint courier
tokens is real but small follow-on work, deferred for the same reason ADR
0005 deferred the board's staff-token gap: it isn't load-bearing for this
phase's acceptance criterion.

### 6. Couriers move via an internal autopilot, not a simulator actor

PHASES.md's Phase 6 froze the simulator as a customer-only client. Rather
than reopening it to add a second actor type mid-phase, dispatch runs its own
Celery-scheduled courier motion: position ticks toward the current
destination and automatic `pick_up`/`depart`/`deliver` calls once ETA
elapses, all real transitions through the same functions the authenticated
HTTP endpoints expose, scaled by `SPEED` like everything else. The courier
API surface is fully real and independently tested (§5 above); the autopilot
is what drives it today in the absence of a courier actor. A future phase
swapping the autopilot for simulator-driven couriers hitting the real HTTP
surface is a client change, not a dispatch change.

## Consequences

- Dispatch's database holds address text (`address_grant.line1`,
  `pending_dropoff.line1`) — allowed for dispatch, never for kitchen. The PII
  boundary is schema-level for kitchen and access-level (the time-box) for
  dispatch; this ADR is the record of that distinction being deliberate.
- `docker compose stop dispatch` mid-rush leaves `pending_dropoff` rows and
  unclaimed `order.ready`/`order.placed` stream backlog; both drain correctly
  on restart, which is the Phase 10 chaos scenario this extraction has to
  survive.
- The batching heuristic and the deferred courier-login flow are both named
  here so neither reads as an oversight later.
