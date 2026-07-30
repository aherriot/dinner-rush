# Dinner Rush — specification

Domain model, state machine, API surface, event catalogue and permissions.
Everything an implementer needs that isn't in [DECISIONS.md](DECISIONS.md)
(slot allocation, streams, outbox) or [DESIGN.md](DESIGN.md) (tokens).

All money is integer cents. All timestamps are `timestamptz`, UTC. All ids are
UUIDv7 except `outbox.id` (bigserial, ordering matters) and `order.code` (a
short human-readable string like `4471`, unique, used in every UI).

---

## 1. Domain model

### 1.1 Front-of-house (Postgres: `front_of_house`)

**`customer`** — `id`, `name`, `email` (unique), `phone`, `created_at`

**`address`** — `id`, `customer_id`, `label`, `line1`, `grid_x` smallint,
`grid_y` smallint, `notes`
> The city is an abstract 100×100 grid, not real geography. No map tiles, no
> network dependency. See [DESIGN.md](DESIGN.md) §10 and `config.example.yaml`.

**`menu_item`** — `id`, `sku` (unique), `name`, `description`,
`base_price_cents`, `prep_seconds`, `bake_seconds`, `oven_slots` smallint
(usually 1; a party size takes 2), `station` (`prep`|`assembly`), `available`
bool, `sort_order`

**`order`** — `id`, `code` (unique), `customer_id`, `address_id`, `status`,
`subtotal_cents`, `delivery_fee_cents`, `total_cents`, `placed_at`,
`accepted_at`, `promised_at`, `ready_at`, `delivered_at`, `rejection_reason`
(`at_capacity`|`item_unavailable`|`outside_range`), `idempotency_key` (unique,
nullable)

**`order_item`** — `id`, `order_id`, `menu_item_id`, `qty`,
`unit_price_cents`, `name_snapshot`, `prep_seconds_snapshot`,
`bake_seconds_snapshot`
> Snapshot the price and durations at order time. An order's history must not
> change when the menu does — a small thing that reads as experience.

**`staff`** — `id`, `name`, `role` (`kitchen`|`manager`), `user_id`

**`outbox`**, **`processed_event`** — see [DECISIONS.md](DECISIONS.md) §0004

### 1.2 Kitchen (Postgres: `kitchen`)

**`oven`** — `id`, `name`, `slot_count` smallint, `status`
(`available`|`down`)

**`oven_slot`** — `id`, `oven_id`, `slot_index`, `order_id` (nullable
occupant), `claimed_at`, `frees_at` — see [DECISIONS.md](DECISIONS.md) §0002
for the claim query and the two indexes that make it correct

**`station`** — `id`, `name`, `kind` (`prep`|`assembly`), `capacity`
smallint, `status`

**`ticket`** — kitchen's own view of an order. `id`, `order_id`, `code`,
`status`, `items` jsonb (snapshot), `total_bake_seconds`, `queued_at`,
`started_at`, `baked_at`, `ready_at`, `oven_slot_id`, `priority` int
> The kitchen does **not** read front-of-house's `order` table. It builds tickets
> from `order.accepted` events. Separate database, separate schema, no shared
> connection string. An agent that gives kitchen a front-of-house DSN has broken the
> project.

**`processed_event`** — kitchen's own idempotency table

### 1.3 Dispatch (Postgres: `dispatch`)

**`courier`** — `id`, `name`, `status`
(`offline`|`idle`|`assigned`|`delivering`), `vehicle` (`bike`|`scooter`),
`speed_cells_per_min` numeric, `shift_started_at`

**`trip`** — `id`, `courier_id`, `order_id`, `code`, `status`
(`assigned`|`picked_up`|`delivering`|`delivered`|`failed`), `pickup_x/y`,
`dropoff_x/y`, `assigned_at`, `picked_up_at`, `delivered_at`, `failed_at`,
`eta_at`, `distance_cells`, `failure_reason`

**`address_grant`** — `id`, `trip_id`, `courier_id`, `dropoff_x`, `dropoff_y`,
`line1`, `granted_at`, `expires_at`, `revoked_at`
> The time-boxed permission from PIZZA.md, made real. Written at assignment,
> revoked on delivery/failure, and independently expiring. §6.2.

Redis holds courier positions (`GEOADD` on key `couriers:live`), the occupancy
cache, and the event streams. Nothing durable.

---

## 2. Order state machine

Phase 2 builds this as an explicit, exhaustively tested FSM. Transitions not in
this table raise `IllegalTransition` — there is no permissive default.

| From | Event | To | Guard | Actor |
| --- | --- | --- | --- | --- |
| — | `place` | `placed` | valid cart, all items available | customer |
| `placed` | `accept` | `accepted` | capacity quote OK | front-of-house |
| `placed` | `reject` | `rejected` | no capacity / item out / out of range | front-of-house |
| `accepted` | `enqueue` | `queued` | ticket created | kitchen |
| `queued` | `start_prep` | `prepping` | station free | kitchen |
| `prepping` | `start_bake` | `baking` | **oven slot claimed** | kitchen |
| `baking` | `finish_bake` | `boxed` | bake timer elapsed | kitchen |
| `boxed` | `mark_ready` | `ready` | all items boxed | kitchen |
| `ready` | `assign` | `assigned` | courier available | dispatch |
| `assigned` | `pick_up` | `picked_up` | courier at pickup | courier |
| `picked_up` | `depart` | `delivering` | — | courier |
| `delivering` | `deliver` | `delivered` | courier at dropoff | courier |
| `delivering` | `fail` | `failed` | no answer / dropped | courier |
| `assigned` | `unassign` | `ready` | courier went offline | dispatch |
| `picked_up` | `unassign` | `ready` | courier went offline | dispatch |

**Terminal:** `delivered`, `rejected`, `failed`.

`late` is **not a state**. It is a derived boolean — `now() > promised_at` and
status not terminal — computed at read time. It never enters this table and
never overwrites `status`. See [DESIGN.md](DESIGN.md) §3.3.

`unassign` returning to `ready` is what makes the courier-offline chaos scenario
work. Note it is legal from `picked_up`: the pizza exists, is in a bag on the
street, and needs a new courier. That case is worth a test.

---

## 3. API surface

Versioned under `/api/v1`. All errors use RFC 7807 `application/problem+json`
with `type`, `title`, `status`, `detail`, `instance`, `correlation_id`.

### 3.1 Front-of-house — public (Django + DRF, port 8000)

| Method | Path | Role | Notes |
| --- | --- | --- | --- |
| `POST` | `/auth/token` | — | returns access + refresh JWT |
| `GET` | `/menu` | any | includes `available`; the shortage scenario flips these |
| `POST` | `/orders` | customer | **`Idempotency-Key` header required.** 201 accepted, **202 with `status: rejected`** when at capacity |
| `GET` | `/orders/{code}` | customer(own) / manager | |
| `GET` | `/orders/{code}/timeline` | customer(own) / manager | ordered event history |
| `GET` | `/board/snapshot` | kitchen / manager | full board state for cold load |
| `WS` | `/ws/orders/{code}` | customer(own) | accepts `?last_event_id=` |
| `WS` | `/ws/board` | kitchen / manager | accepts `?last_event_id=` |

> **Rejection is not an error.** `POST /orders` returning "we can't cook this"
> is a successful, well-formed, designed response body — not a 4xx, not a 503.
> Getting this wrong inverts the whole thesis.

### 3.2 Front-of-house — admin (manager only)

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/admin/ovens/{id}/status` | `{"status": "down"\|"available"}` |
| `POST` | `/admin/menu/{sku}/availability` | ingredient shortage |
| `POST` | `/admin/scenarios/{name}/start` | chaos; see `config.example.yaml` |
| `POST` | `/admin/scenarios/{name}/stop` | |
| `POST` | `/admin/speed` | `{"speed": 1\|10\|60}` |

### 3.3 Kitchen (FastAPI, port 8001)

| Method | Path | Caller | Notes |
| --- | --- | --- | --- |
| `GET` | `/queue` | front-of-house, board | tickets ordered by priority |
| `GET` | `/ovens` | front-of-house, board | slot occupancy + `frees_at` |
| `POST` | `/capacity/quote` | front-of-house | `{items[]}` → `{can_accept, promised_at, queue_depth, projected_wait_s}` |
| `POST` | `/tickets/{id}/advance` | staff | manual override, manager/kitchen only |
| `GET` | `/healthz` `/readyz` | compose | |

`POST /capacity/quote` is the backpressure decision point. It is a **read-only
projection** — it must not reserve anything. The reservation happens later when
the ticket actually claims a slot, and the gap between quote and claim is why
`rejected` can still occur after a positive quote. Say that in the ADR.

### 3.4 Dispatch (FastAPI, port 8002)

| Method | Path | Caller | Notes |
| --- | --- | --- | --- |
| `GET` | `/trips` | board | active trips |
| `GET` | `/couriers` | board | positions, statuses |
| `POST` | `/couriers/{id}/status` | courier | `online`/`offline` |
| `POST` | `/couriers/{id}/position` | courier | `{x, y}` → `GEOADD` |
| `GET` | `/couriers/me/trips` | courier | own trips only |
| `GET` | `/trips/{id}/dropoff` | courier | **403 unless a live grant exists** — §6.2 |
| `POST` | `/trips/{id}/pickup` | courier | |
| `POST` | `/trips/{id}/deliver` | courier | |
| `POST` | `/trips/{id}/fail` | courier | `{reason}` |
| `GET` | `/healthz` `/readyz` | compose | |

### 3.5 Contracts

Every service publishes OpenAPI at `/openapi.json`. The frontend client and the
simulator client are **generated** into `apps/web/src/api/` and
`services/simulator/client/`. Hand-written clients are a defect — drift between
a service and its consumers is exactly what this project claims to manage. CI
regenerates and fails on a diff.

---

## 4. Event catalogue

Envelope, versioning and delivery semantics: [DECISIONS.md](DECISIONS.md) §0004.
Streams: `events:order`, `events:oven`, `events:courier`.

All payloads below are the `payload` field; the envelope wraps them.

| Event | Producer | Payload | Consumers |
| --- | --- | --- | --- |
| `order.placed` | front-of-house | `code, customer_id, items[], total_cents, grid_x, grid_y` | analytics, ws |
| `order.accepted` | front-of-house | `code, promised_at, items[]` | **kitchen**, analytics, ws |
| `order.rejected` | front-of-house | `code, reason, queue_depth` | analytics, ws |
| `order.queued` | kitchen | `code, position, projected_start_at` | front-of-house, ws |
| `item.started` | kitchen | `code, item_id, station` | ws |
| `order.baking` | kitchen | `code, oven_id, slot_index, frees_at` | front-of-house, ws |
| `order.baked` | kitchen | `code, actual_bake_s` | front-of-house, analytics, ws |
| `order.ready` | kitchen | `code, grid_x, grid_y, ready_at` | **dispatch**, front-of-house, notifier, analytics, ws |
| `oven.slot_freed` | kitchen | `oven_id, slot_index` | kitchen(alloc), ws |
| `oven.down` / `oven.restored` | kitchen | `oven_id, slot_count` | front-of-house, ws |
| `courier.online` / `courier.offline` | dispatch | `courier_id, x, y` | dispatch(reassign), ws |
| `courier.assigned` | dispatch | `code, courier_id, eta_at, distance_cells` | front-of-house, notifier, ws |
| `order.picked_up` | dispatch | `code, courier_id, at` | front-of-house, notifier, ws |
| `order.delivering` | dispatch | `code, courier_id, eta_at` | front-of-house, ws |
| `order.delivered` | dispatch | `code, courier_id, total_elapsed_s` | front-of-house, analytics, notifier, ws |
| `order.failed` | dispatch | `code, reason` | front-of-house, analytics, ws |
| `order.late` | front-of-house | `code, promised_at, projected_at` | analytics, ws |
| `station.down` | kitchen | `station_id` | ws |

**`order.ready` is the showpiece fan-out** — five consumers, none aware of each
other: dispatch assigns a courier, front-of-house advances the order, the notifier
tells the customer, analytics records cook time, and the websocket layer
repaints three surfaces. Make it easy to point at.

**Consumer/side-effect classification** — required by
[DECISIONS.md](DECISIONS.md) §0004, because the guarantee differs:

| Consumer | Side effect | Guarantee |
| --- | --- | --- |
| kitchen, front-of-house, dispatch, analytics | Postgres writes | **effectively-once** (dedup in the same txn) |
| notifier | outbound notification | **at-least-once** — may duplicate, and that is stated, not hidden |
| ws-fanout | in-memory push | at-least-once, idempotent by `event_id` client-side |

---

## 5. Pricing and timing

Deliberately simple — this is the worthless-CRUD half and must not absorb time.

```
subtotal      = Σ(unit_price_cents × qty)
delivery_fee  = 299 flat, waived above 4000
total         = subtotal + delivery_fee
promised_at   = accepted_at + projected_wait_s + drive_estimate_s + buffer_s
```

`projected_wait_s` comes from `POST /capacity/quote`. `drive_estimate_s` is
Chebyshev grid distance ÷ courier speed. `buffer_s` is config (default 180).

**All durations are divided by `SPEED` at the point of use** — never at the
point of storage. A stored `bake_seconds` of 420 is always 420; at `SPEED=10` a
timer is set for 42 real seconds. There is no virtual clock, per PIZZA.md.
Every timeout, TTL and heartbeat stays on wall time and keeps meaning what it
says. An agent that stores pre-scaled durations has broken this.

---

## 6. Roles and permissions

### 6.1 Matrix

| Resource | Customer | Kitchen | Courier | Manager |
| --- | --- | --- | --- | --- |
| Own order + status + ETA | ✅ | — | — | ✅ |
| Any customer's order | ❌ | ❌ | ❌ | ✅ |
| Customer name/phone/address | own | **❌** | **grant only** | ✅ |
| Kitchen queue, oven state | ❌ | ✅ | ❌ | ✅ |
| Courier positions | own courier once picked up | ❌ | own | ✅ |
| Own trips | ❌ | ❌ | ✅ | ✅ |
| Admin / chaos / speed | ❌ | ❌ | ❌ | ✅ |
| Analytics | ❌ | ❌ | ❌ | ✅ |

**Kitchen staff never see customer PII.** Tickets carry `code` and items only.
This is a schema-level guarantee — the PII is not in kitchen's database at all,
so there is nothing to leak. That is a much better answer than a filtered
serializer.

### 6.2 The time-boxed address grant

The one genuinely sharp permission rule, and worth its own test file.

- **Granted** when `courier.assigned` fires: a row with
  `expires_at = now() + grant_ttl` (config, default 3600s ÷ SPEED)
- **Revoked** on `deliver` or `fail`: `revoked_at = now()`
- **Checked** on every `GET /trips/{id}/dropoff`:
  `courier_id` matches ∧ `revoked_at IS NULL` ∧ `expires_at > now()`

Four tests, all four must exist:

1. before assignment → **403**
2. during assignment → **200**, correct address
3. after delivery → **403**
4. after `expires_at` with the trip still open → **403**

Case 4 is the one people forget, and it is the one that proves the grant is
time-boxed rather than merely lifecycle-boxed.

### 6.3 Service-to-service auth

Front-of-house signs RS256 JWTs and publishes a JWKS at `/.well-known/jwks.json`.
Kitchen and dispatch verify against it and cache the key. Claims: `sub`, `role`,
`scope[]`, `exp`, `correlation_id`.

**The simulator authenticates exactly like a real client** — `POST /auth/token`
with seeded credentials, one token per simulated actor. It has no service
credentials, no database credentials, and no privileged scope. This is the
premise of the whole project and it is enforced in `compose.yaml`, not by
convention. See [CLAUDE.md](../CLAUDE.md) §5.

---

## 7. Metrics

Exposed at `/metrics` on every service, scraped by Prometheus, surfaced on the
board's status bar.

| Metric | Type | Why |
| --- | --- | --- |
| `orders_placed_total{outcome}` | counter | `accepted` vs `rejected` — the headline |
| `order_rejections_total{reason}` | counter | proves backpressure is deliberate |
| `kitchen_queue_depth` | gauge | the number that climbs during a rush |
| `oven_slots_occupied` / `_total` | gauge | capacity, live |
| `order_cook_seconds` | histogram | promised vs actual |
| `promise_error_seconds` | histogram | **p50/p95 promise accuracy** |
| `orders_late_ratio` | gauge | status bar |
| `stream_pending{group}` | gauge | `XPENDING` — the backlog that visibly drains |
| `slot_claim_contention_total` | counter | how often claims raced |
| `http_request_duration_seconds` | histogram | standard |

`promise_error_seconds` and `stream_pending` are the two that make claims
falsifiable. `stream_pending` is the graph to point at during the
`docker compose stop dispatch` demo — it climbs while dispatch is dead and
drains on recovery, which is the entire argument for Redis Streams over pub/sub.
