# Dinner Rush — a simulated pizza operation

Orders arrive, a capacity-constrained kitchen cooks them, couriers deliver them.
The whole thing runs as a **live simulation you can watch and break**.

Sibling ideas: [IDEAS.md](IDEAS.md), [PHOTOSYNTH.md](PHOTOSYNTH.md). Practices
and build order transfer from [TALLY.md](TALLY.md).

---

## The one decision that makes this work

**Build the real system. Make the simulator an ordinary client of it.**

The simulator gets no privileged access, no direct database writes, no internal
imports. It authenticates and calls the same public API a real customer, courier
or kitchen tablet would:

```
simulator ──HTTP──► front-of-house API ──► the real system
          ──HTTP──► courier API
          ──HTTP──► kitchen display API
```

Three consequences, and they're the whole argument for this project:

1. **The load is real load.** A dinner rush in the simulator is a genuine
   concurrency test, not a fixture. When you claim it handles 40 orders/minute,
   you can prove it on your laptop.
2. **Nothing is fake except the people.** Every order really goes through the
   queue, the oven allocator, and the dispatcher. Compare this to Photosynth,
   where the diagnosis itself was heuristic theatre.
3. **Real users would change nothing.** If you ever hosted it, you'd delete the
   simulator and the system is untouched. Say that in the README.

---

## Why three services, honestly

The three do genuinely different kinds of work — that's the test, and this
domain passes it more cleanly than any other idea in the folder.

| Service     | Stack            | The work it does                                                                                | Why it can't live in front-of-house                                                      |
| ----------- | ---------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `front-of-house` | Django + DRF | Menu, customers, orders, staff, pricing, auth, admin                                            | —                                                                                        |
| `kitchen`   | FastAPI + Celery | **Constrained-resource scheduling.** Finite oven slots, per-item cook times, station contention | It runs a tick loop and holds contended state. It's a scheduler, not a CRUD app          |
| `dispatch`  | FastAPI          | **Geospatial assignment.** Nearest available courier, trip batching, ETA and re-ETA             | Different data structures (Redis GEO), different scaling profile, different read pattern |
| `simulator` | Python, no DB    | Spawns customers, drives couriers, injects chaos                                                | It's a client. It must be separate or the whole premise collapses                        |

The kitchen is the interesting one and the reason to build this. **Oven slots
are a genuinely contended resource** — two orders racing for the last slot is a
real distributed systems problem with a real solution, not a contrived one.

---

## Order lifecycle

```
placed ──► accepted ──► queued ──► prepping ──► baking ──► boxed ──► ready
                │                                                      │
                │                                                assigned
                ▼                                                      │
            rejected                                              picked_up
          (at capacity)                                                │
                                                                  delivering
                                                                       │
                                            ┌──────────────────────────┤
                                            ▼                          ▼
                                        delivered                   failed
                                                              (no answer, dropped)
```

`rejected` is the important state. A restaurant at capacity **refuses orders**
— that's backpressure expressed in the domain, and it's the single most
valuable thing this project demonstrates.

---

## What Redis actually does

Four distinct jobs, none of them decorative. Flush it and the system rebuilds
from Postgres — nothing durable lives here.

| Job                      | Mechanism                                                                                                       |
| ------------------------ | --------------------------------------------------------------------------------------------------------------- |
| **Oven slot allocation** | Slot reservation with `SET NX EX` locks. Two orders, one slot, one winner                                       |
| **Courier positions**    | `GEOADD` / `GEOSEARCH` — "nearest available courier within 3km" is one command, and it's the right tool         |
| **Live boards**          | Pub/sub → websockets. Kitchen display, dispatch map and customer tracker all repaint from the same event stream |
| **Rolling metrics**      | Counters and sorted sets: orders/min, current queue depth, p50/p95 promise accuracy                             |
| **Celery broker**        | Cooking stages, ETA recalculation, notifications                                                                |

---

## Events

`order.placed` · `order.accepted` · `order.rejected` · `order.queued`
`item.started` · `order.baked` · `order.ready` · `courier.assigned`
`order.picked_up` · `order.delivered` · `order.late` · `order.failed`
`oven.slot_freed` · `courier.online` · `courier.offline` · `station.down`

The showpiece fan-out is `order.ready` → dispatch assigns a courier, the customer
is notified, the kitchen board clears the slot, the oven allocator releases
capacity, and analytics records cook time. **Five consumers, none aware of each
other.**

The second-best is `courier.offline` mid-delivery: reassign the trip, re-quote
the ETA, notify the customer, flag the courier for the manager.

---

## Handling time

Do **not** build a virtual clock. Distributed virtual time is genuinely hard —
Celery countdowns, beat schedules, Redis TTLs and websocket heartbeats all use
wall time, and reconciling them will eat the project.

Instead: **scale the durations, not the clock.** Cook times, drive times and
customer think-times all come from config. A `SPEED=10` run makes a 7-minute
margherita take 42 real seconds. Everything stays on wall time, every timeout
still means what it says, and you still get a dinner rush in ninety seconds.

---

## Roles

| Role              | Sees                                                                             |
| ----------------- | -------------------------------------------------------------------------------- |
| **Customer**      | Their own order, live status, ETA, courier position once picked up. Nothing else |
| **Kitchen staff** | The kitchen display — queue, oven occupancy, what to start next. No customer PII |
| **Courier**       | Their assigned trips, pickup and dropoff. Not the customer's order history       |
| **Manager**       | Everything, plus chaos controls and the analytics dashboard                      |

Courier access to a customer address is **time-boxed** — granted at assignment,
revoked on delivery. That's the one genuinely sharp permission rule here, and
it's worth a test.

---

## The demo

One screen, four panels, and a speed control. This is the whole pitch.

```
┌───────────────┬────────────────────────────┬──────────────────┐
│ ORDER FEED    │ KITCHEN                    │ DISPATCH MAP     │
│               │                            │                  │
│ #4471 placed  │ Oven 1 ██████░░  2 slots   │    ○ courier     │
│ #4470 baking  │ Oven 2 ████████  FULL      │  ○      ●        │
│ #4469 ready   │ Oven 3 ░░ DOWN             │      ●    ○      │
│ #4468 rejected│                            │   ●              │
│               │ Queue: 14   Wait: 22 min   │ 6 active trips   │
├───────────────┴────────────────────────────┴──────────────────┤
│ ⏱ 19:42  SPEED [1x] [10x] [60x]   38 ord/min   p95 late: 8%  │
│ CHAOS: [Friday rush] [Oven down] [Courier offline] [Cheese out]│
└───────────────────────────────────────────────────────────────┘
```

**The 45-second story.** Start at 1x, calm, orders flowing through. Hit
**Friday rush** — order rate triples. Watch the kitchen queue climb, watch
promised ETAs stretch from 25 to 40 minutes, watch the system start returning
`rejected` at the door rather than accepting orders it can't cook. Then hit
**Oven down** and watch capacity drop and the queue reorder. Then bring it back
and watch it drain.

That's a portfolio project demonstrating **backpressure and graceful
degradation under load**, live, on one screen. Almost nothing in a junior or
mid portfolio does that.

**Chaos scenarios**, all just simulator behaviours plus admin API calls:

| Scenario                 | What it exercises                                                               |
| ------------------------ | ------------------------------------------------------------------------------- |
| Friday rush              | Backpressure, queue growth, rejection at capacity                               |
| Oven goes down           | Capacity reduction, re-scheduling, ETA re-quoting                               |
| Courier offline mid-trip | Reassignment, event fan-out, customer notification                              |
| Ingredient shortage      | Menu availability propagating to the storefront                                 |
| Dispatch service killed  | Degraded mode — orders still cook, delivery stalls, recovery drains the backlog |

That last one is the real test, and it's the one to record: `docker compose stop
dispatch`, keep taking orders, bring it back, watch it catch up.

---

## Build order

1. **Monolith.** Django, place an order, fake instant cooking. Full UX end to end.
2. **Real cook times in Celery.** Stages, status polling, the customer tracker.
3. **Extract `kitchen`** with genuine oven capacity and contention. This is where
   the project becomes interesting — do not skip ahead to delivery.
4. **Simulator v1** — synthetic customers only. Now you have load.
5. **Extract `dispatch`** with Redis GEO and courier assignment.
6. **The board and chaos controls.** The demo is a feature; budget for it.

Stop after 4 and it's still a real project with a real story.

---

## Honest weak spots

**Food delivery is the most-cloned microservices tutorial domain there is.**
An interviewer has seen twenty Uber Eats clones. The CRUD half of this project
is _worthless_ as a differentiator — the oven contention, the backpressure and
the chaos demo are the entire value. Lead with them in the README, put the
rush GIF at the top, and never describe it as "a food delivery app."
