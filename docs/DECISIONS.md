# Load-bearing technical decisions

Three designs that the rest of the project leans on. These become ADRs 0002–0004
once the repo exists. Written before any code because getting them wrong is
expensive and getting them right is most of the portfolio value.

---

## 0002 — Oven slots: Postgres is the authority, Redis is a cache

### The problem with the original design

`SET NX EX` is a **lease**: a promise about state, held for a duration, with no
relationship to the actual state. When the lease expires — GC pause, slow query,
a bake that runs longer than the TTL, a stalled container — the holder still
believes it owns the slot while a second claimer legitimately acquires it. You
now have two orders in a one-slot oven and nothing in the system that can detect
it. This is Kleppmann's objection to Redlock, and it applies here in its
simplest form.

### The design

The claim **is** the state. There is no lease.

```sql
CREATE TABLE oven (
  id         uuid PRIMARY KEY,
  name       text     NOT NULL,
  slot_count smallint NOT NULL,
  status     text     NOT NULL DEFAULT 'available'   -- available | down
);

CREATE TABLE oven_slot (
  id         uuid PRIMARY KEY,
  oven_id    uuid     NOT NULL REFERENCES oven(id),
  slot_index smallint NOT NULL,
  order_id   uuid     NULL,          -- occupant; NULL = free
  claimed_at timestamptz NULL,
  frees_at   timestamptz NULL,
  UNIQUE (oven_id, slot_index)
);

-- The invariant that protects you even from your own bugs:
CREATE UNIQUE INDEX one_slot_per_order
  ON oven_slot (order_id) WHERE order_id IS NOT NULL;
```

Claiming is one statement:

```sql
UPDATE oven_slot
   SET order_id = %(order_id)s,
       claimed_at = now(),
       frees_at   = now() + %(cook_duration)s
 WHERE id = (
    SELECT s.id
      FROM oven_slot s
      JOIN oven o ON o.id = s.oven_id
     WHERE s.order_id IS NULL
       AND o.status = 'available'
     ORDER BY s.oven_id, s.slot_index
       FOR UPDATE OF s SKIP LOCKED
     LIMIT 1
 )
RETURNING id, oven_id, slot_index;
```

**Zero rows returned means the kitchen is at capacity, which means `rejected`.**
Backpressure falls directly out of the storage layer rather than being computed
alongside it. That is a very good sentence to be able to say out loud.

### Why this is better, point by point

- **No lease to expire.** Occupancy is a committed row, not a timed promise.
- **`SKIP LOCKED` is fast under contention, not merely correct.** Concurrent
  claimers skip past each other's locked rows onto different slots instead of
  serialising into a queue. Correctness *and* throughput from one clause.
- **The partial unique index is a second line of defence.** Even an application
  bug cannot double-book an order into two slots — the database refuses.
- **Crash safety without lock expiry.** If the kitchen process dies mid-bake the
  row still reads occupied. A reaper sweeps `frees_at < now() - grace`. That is
  *reconciliation against an authority*, not a lock timing out, and it is
  idempotent — running it twice changes nothing.

Redis's role becomes honest and matches what PIZZA.md already claims: an
`oven:occupancy` hash written after commit and read by the board at 10 Hz. Flush
it and the next tick rebuilds it from Postgres. Nothing durable lives there.

### The test that is the portfolio piece

```python
@pytest.mark.repeat(200)
async def test_last_slot_has_exactly_one_winner(oven_with_one_free_slot):
    orders = [uuid4() for _ in range(50)]
    results = await asyncio.gather(*(claim_slot(o) for o in orders))

    assert sum(r is not None for r in results) == 1
    assert await count_occupied_slots() == 1
```

Plus a Hypothesis property test: across any interleaving of claims and releases,
occupied slots never exceed `slot_count` and no order holds two slots.

### The branch that proves you knew

Keep `spike/redis-lease-allocation` alive with a **deterministic** failure test:
claim with `SET NX EX 1`, sleep past the TTL to simulate a stalled process, let
a second claimer succeed, assert two orders occupy a one-slot oven. Being able
to show the failure mode you avoided is worth more than the fix.

---

## 0003 — Redis Streams for the event bus (and why not Kafka)

### Three messaging jobs, deliberately not one system

| Job | Shape | Tool |
| --- | --- | --- |
| Scheduled / delayed work — cook stage transitions, ETA recalcs, the slot reaper | point-to-point, one consumer, needs countdowns and retries | **Celery** |
| Domain events — `order.ready` fanning out to five consumers | pub/sub with replay and at-least-once | **Redis Streams** |
| Live UI push | derived from the event bus, not its own system | **websockets over a Streams consumer** |

Say this explicitly in the ADR, or the presence of both Celery and Streams looks
like two brokers chosen by accident.

### Why not Kafka

Kafka's differentiators — partition-scale ordering, log compaction, tiered
storage, multi-DC replication, seven-figure throughput — are all unreachable at
40 orders/minute on a laptop. Adopting it here is **unfalsifiable**: no
Kafka-specific benefit could be demonstrated. Against that, Redpanda costs 1–2 GB
and real startup time on a machine already running Postgres, Redis, three Python
services, a simulator, Grafana and Vite, which fights the `make up` budget
directly. NATS JetStream is the honest middle option and still loses: another
container and dependency for marginal gain over infrastructure already present.

State the migration trigger so the decision is sized rather than merely
preferred: sustained throughput past ~50k events/sec, retention beyond days, or
consumers needing independent multi-week replay. None apply.

### Topology

One stream per **aggregate type**, not per event type and not one global stream:

```
events:order      events:oven      events:courier
```

Per-aggregate ordering is the only ordering guarantee actually needed
(`order.baked` before `order.ready` for the same order); cross-aggregate
ordering is neither needed nor promised. One stream per event type would force
consumers into dozens of reads.

Consumer groups: `cg:dispatch`, `cg:notifier`, `cg:analytics`, `cg:ws-fanout`,
`cg:kitchen`. Loop is `XREADGROUP` → handle → `XACK`; crashing before the ack
means redelivery, which is exactly why 0004 exists.

**Recovery** is `XAUTOCLAIM` on a timer, reclaiming messages pending longer than
N seconds from dead consumers. About ten lines, and it is the entire mechanism
behind the `docker compose stop dispatch` demo.

**Backlog is observable.** `XPENDING` per consumer group is a metric, a board
panel, and the thing that visibly drains on recovery. This is the single most
important reason to prefer Streams over pub/sub: with pub/sub there is no
backlog to drain, so the headline demo would silently do nothing.

Trim with `XADD … MAXLEN ~ 100000` so a long rush cannot fill the disk.

### Websocket replay

The browser sends `last_event_id` on connect. The server `XRANGE`s from there,
flushes the gap, then switches to live. Refresh mid-rush and you miss nothing —
a visible, demoable correctness property that costs about twenty lines.

### What if Redis dies?

Worth having the answer ready. Celery tasks in flight are lost, mitigated by
`acks_late` plus retry. Stream entries survive if AOF is on. Postgres is
untouched, and — because of the outbox below — **the relay simply re-publishes
unacknowledged events from the outbox table**. Redis is recoverable state, not
a system of record. That property is a direct consequence of 0004.

---

## 0004 — Envelope, outbox, idempotency

### The envelope

```python
class EventEnvelope(BaseModel):
    event_id:       UUID          # idempotency key
    event_type:     str           # "order.ready"
    event_version:  int           # 1
    occurred_at:    datetime      # domain time, not publish time
    aggregate_type: str           # "order"
    aggregate_id:   UUID
    sequence:       int           # per-aggregate monotonic
    correlation_id: UUID          # whole causal chain; threads into OTel
    causation_id:   UUID | None   # the event that caused this one
    producer:       str           # "front_of_house@1.4.2"
    payload:        dict
```

`sequence` earns its place: a per-aggregate monotonic counter lets a consumer
notice it has already seen a *later* event and drop a stale redelivery. That is
out-of-order protection layered on top of deduplication, and it is three lines.

`correlation_id` and `causation_id` together let you reconstruct the full fan-out
tree of a single order — which is what makes the Phase 9 trace waterfall
readable rather than a pile of disconnected spans.

### Versioning policy

Additive-only within a major version; consumers ignore unknown fields. A
breaking change is a **new event type** (`order.ready.v2`) published alongside
the old one for a deprecation window. Schemas are Pydantic models in the shared
package, exported to JSON Schema, with a CI check that asserts backward
compatibility against the committed schemas. Having a *written* policy is most
of the signal here — very few portfolio projects have one at all.

### Transactional outbox

```sql
CREATE TABLE outbox (
  id           bigserial PRIMARY KEY,
  event_id     uuid NOT NULL UNIQUE,
  stream       text NOT NULL,            -- events:order
  envelope     jsonb NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz NULL
);
CREATE INDEX outbox_unpublished ON outbox (id) WHERE published_at IS NULL;
```

The event row is written **in the same transaction as the state change**. No
committed order without its event; no event for an order that rolled back.

The relay:

```sql
SELECT * FROM outbox
 WHERE published_at IS NULL
 ORDER BY id
   FOR UPDATE SKIP LOCKED
 LIMIT 100;
```

`SKIP LOCKED` again, so multiple relay workers parallelise safely. Wake it
instantly with `LISTEN/NOTIFY` on commit and keep a 100 ms poll as the fallback
— instant in the happy path, self-healing if a notification is ever missed.
That fallback is also what makes Redis loss recoverable.

### Consumer-side idempotency

```sql
CREATE TABLE processed_event (
  consumer_group text NOT NULL,
  event_id       uuid NOT NULL,
  processed_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (consumer_group, event_id)
);
```

The handler does `INSERT … ON CONFLICT DO NOTHING` **in the same transaction as
its side effect**. Zero rows affected means already processed: ack and move on.

### Be precise about what this guarantees

This is the sentence that separates people who have run event-driven systems
from people who have read about them:

> **Effectively-once for database side effects. At-least-once for external
> effects.** A consumer that writes to Postgres is deduplicated by the same
> transaction that does the work. A consumer that sends a notification can send
> it twice, and the design accepts that rather than pretending otherwise.

Claiming exactly-once delivery is the tell. Naming the boundary precisely, and
knowing which of your five consumers sits on each side of it, is the opposite.

---

## Where this lands in the plan

| Decision | Phase |
| --- | --- |
| 0004 envelope, outbox, idempotency | **3** — before any extraction, so it is built once rather than retrofitted into three services |
| 0003 Streams, consumer groups, replay | **3**, with `XAUTOCLAIM` recovery proven in **10** |
| 0002 slot allocation | **4**, the centrepiece, with the contention test in CI from day one |

Optional and genuinely risky: put the bus behind a narrow port
(`publish(envelope)` / `subscribe(group, handler)`) and add a Kafka adapter in a
late phase, selectable by env var. Only worth it if the abstraction stays honest
about differing delivery semantics — a "generic bus" interface that pretends
Kafka and Redis behave identically is worse than committing to one. Build the
port, ship one adapter, and add the second only if time is genuinely spare.
