# 0003 — The event spine: envelope, outbox, streams, websocket fanout

## Status

Accepted.

## Context

Phase 3 builds the infrastructure every later phase leans on (CLAUDE.md §2,
PHASES.md Phase 3): a real cook-progression pipeline on Celery, the event
envelope and outbox from DECISIONS.md §0004, Redis Streams per §0003, and a
websocket fanout that resumes from a last-seen event id. Getting this right
now means the outbox and idempotency patterns are built once, in one service,
rather than retrofitted into three services after Phases 4 and 7 extract
`kitchen` and `dispatch`.

Two things needed a decision beyond what DECISIONS.md already specifies to
the SQL: how much of the event catalogue the front-of-house monolith can honestly
produce before those services exist, and which of the classified consumers
(SPEC.md §4) actually gets built now versus deferred.

## Decisions

### 1. Front-of-house produces the whole happy-path event chain, honestly labelled

Kitchen and dispatch don't exist until Phases 4 and 7, so `front_of_house.orders.tasks`
still walks an accepted order all the way to `delivered` itself — same as the
Phase 2 fake-progression thread it replaces, just on Celery with real
per-item prep/bake seconds instead of fixed delays. Every step still fires
its `EventEnvelope` with `producer: "front_of_house@0.1.0"`, including the ones the
catalogue eventually attributes to kitchen (`order.baking`, `order.baked`,
`order.ready`) — the event *shape* is real and stable now; only the
*producer* changes at extraction time. Fields that depend on infrastructure
that doesn't exist yet (`oven_id`, `slot_index`, `courier_id`) carry explicit
placeholder values (`"sim-oven-1"`, `"sim-courier-1"`) rather than being
omitted, so the payload schema itself doesn't need to change in Phase 4/7.

Legs with no catalogue event yet (`start_prep`, `assign`, `pick_up`,
`depart`) still transition the FSM and write `OrderStatusEvent` for the REST
timeline; they simply don't publish to the outbox. This is a real gap, not
an oversight — the catalogue's granularity assumes kitchen and dispatch own
that state, and inventing an event type for it now would need retracting
later.

### 2. Two consumer groups now, not five

SPEC.md §4's classification table lists five conceptual consumers
(`kitchen`, `dispatch`, `notifier`, `analytics`, `ws-fanout`). Kitchen and
dispatch aren't separate consumers yet (see above), and `notifier` has
nothing to notify — no email/SMS is ever being built (CLAUDE.md
"Explicitly not building"). That leaves two real consumer groups, and they
were chosen specifically because they sit on *opposite sides* of the
effectively-once/at-least-once boundary DECISIONS.md §0004 asks to be able
to name precisely:

- **`cg:analytics`** writes to Postgres (`EventTypeCounter`) and must be
  effectively-once, so it dedupes via `processed_event` in the same
  transaction as the increment.
- **`cg:ws-fanout`** pushes to an in-memory Channels group and is
  at-least-once by design — the browser dedupes by `event_id` client-side
  (`OrderTracker.tsx`'s `lastEventIdRef`), so there is nothing to make
  idempotent server-side.

Having exactly one consumer of each kind is enough to prove both guarantees
with a test; a third consumer of either kind would be repetition, not new
coverage.

### 3. Each event-spine process is its own container, sharing the front-of-house image

`relay`, `stream_consumer --group cg:analytics`, `stream_consumer --group
cg:ws-fanout` and the Celery worker are separate `compose.yaml` services
(`outbox-relay`, `consumer-analytics`, `consumer-ws-fanout`,
`celery-worker`), not threads inside the `front-of-house` process. Same image,
different `command:`. This costs nothing extra to build and buys the Phase
10 chaos demo: any one of them can be `docker compose stop`ped independently
to show its specific failure mode (backlog growing on `cg:analytics`,
websocket pushes stalling on `cg:ws-fanout`) without taking the API down.
They use a liveness-only healthcheck (`python -c "exit(0)"`) rather than a
real one — there's no HTTP endpoint to poll, and pretending to measure queue
health here would just duplicate what `stream_pending` (Phase 9) is for.

### 4. Worker loops swallow and retry rather than crash

`manage.py relay` and `manage.py stream_consumer` catch exceptions per
iteration and keep looping instead of letting the process die — a missing
table (because `make up`'s `migrate` step hasn't run yet) or a transient
Postgres blip is retried, not fatal. A consumer that fails to process a
message simply doesn't ack it, so the message stays pending and gets
reclaimed by `XAUTOCLAIM` on the next pass. This is what makes the
containers stay "healthy" (in the shallow liveness sense above) through the
window between `docker compose up` and `migrate`, and it's the same
self-healing property the outbox relay's poll fallback already has for a
missed `NOTIFY`.

## Consequences

- Phase 4 (kitchen extraction) inherits `order.baking`/`order.baked`/
  `order.ready` as an already-stable contract — the work is changing who
  publishes them and adding real oven-slot data, not designing the events.
- Phase 7 (dispatch extraction) similarly inherits the shape gap: it must
  *add* `courier.assigned`, `order.picked_up`, `order.delivering` to the
  catalogue rather than just changing their producer, since front-of-house never
  produced them.
- `dinner_rush_core.outbox` and `dinner_rush_core.streams` take a plain
  DB-API cursor / redis-py client rather than an ORM, specifically so kitchen
  (SQLAlchemy) and dispatch (SQLAlchemy) reuse them unmodified in Phase 4/7.
- The `outbox`/`processed_event` Django models set `db_table` explicitly to
  match the SQL in DECISIONS.md §0004 — the generic core functions assume
  those table names by default in every service, not just front-of-house's.

## Alternatives considered

**Model kitchen/dispatch as separate Celery task modules now, even though
those services don't exist.** Rejected — it would produce a git history that
looks like the extraction already happened, which is the opposite of
CLAUDE.md §7's point that the extractions must be real refactor commits, not
directories appearing fully formed.

**Skip `cg:analytics` and only build `cg:ws-fanout`, since the websocket is
the visible feature.** Rejected — the whole point of Phase 3 is proving the
effectively-once/at-least-once distinction with a real test, and
`ws-fanout` alone only demonstrates the at-least-once half.

**Use Postgres `LISTEN/NOTIFY` exclusively, no poll fallback.** Rejected —
DECISIONS.md §0004 already specifies the poll as what makes a missed
notification (or a Redis restart) self-healing; dropping it would silently
reintroduce the failure mode Streams was chosen to avoid.
