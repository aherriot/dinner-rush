# 0009 — Observability: one collector, a threaded trace, and a real load number

## Status

Accepted.

## Context

Phases 0–8 built every claim this project makes — contention-safe slot
allocation, genuine backpressure, a dispatch service that can die mid-demo
without losing an order — but none of it was falsifiable. `make load` was a
stub that exited 1. There was no way to view a trace, no Prometheus metric
existed despite SPEC.md §7 specifying ten of them, and the board's own
`ordersPerMinute`/`p95LatePercent` tiles were explicitly commented as
approximations standing in for numbers this phase was supposed to build
(ADR 0008 §6). Four decisions were made closing that gap.

## Decisions

### 1. Every process's telemetry goes through one OTel collector, not per-process Prometheus scraping

SPEC.md §7 says "exposed at `/metrics` on every service" — read literally,
that means one endpoint per container. This project runs many OS processes
per logical service: front-of-house alone is the web process plus a Celery
worker, an outbox relay, and seven stream consumers. A domain metric like
`order_cook_seconds` is recorded inside kitchen's Celery worker, a different
container from the one that would serve `/metrics`. A raw
`prometheus_client` registry doesn't share state across processes without
its file-based multiprocess mode — real operational complexity bought for no
benefit here.

Instead, every process calls one shared bootstrap
(`dinner_rush_core.observability.setup_otel`) that exports both traces and
metrics over OTLP to a single `otel-collector` container. The collector's
`prometheus` exporter is the one thing Prometheus actually scrapes
(`observability/prometheus.yml` — one target, `otel-collector:8889`). The
intent behind SPEC.md §7 — every service's metrics visible to Prometheus —
holds; the mechanism is a fan-in, not one endpoint per container.

Gauges that reflect live external state (`kitchen_queue_depth`,
`oven_slots_occupied`, `stream_pending`) are `ObservableGauge` callbacks that
query Postgres/Redis directly at each collection tick, which sidesteps the
cross-process problem a second way: the value is always read fresh from the
system of record, not accumulated in whichever process happened to change
it.

`stream_pending`'s first version read only `XPENDING`'s count, which is
"read but not yet acked" — exactly right for a consumer that's stuck or
crashed mid-processing, and nothing else. Actually running the
`docker compose stop dispatch` demo caught the gap: a *fully stopped*
consumer never issues `XREADGROUP` at all, so nothing it hasn't read ever
becomes "pending" no matter how far behind it falls — `XINFO GROUPS`'
`lag` field is the one that grows in that case, and `XPENDING` alone stayed
at zero throughout the whole outage. `dinner_rush_core.streams.backlog`
now sums `pending + lag`, so the metric answers "how far behind is this
consumer group" regardless of which of the two ways it got there.

Fixing the counting still wasn't enough to make the demo work — running it
end to end (not just checking Prometheus had *a* value) surfaced a second,
more basic problem: `stream_pending{group="cg:dispatch"}` was an
`ObservableGauge` living inside *dispatch's own process*. The one moment
this metric needs to keep moving is precisely the one where the process
computing it no longer exists. `docker compose stop dispatch` didn't just
stop dispatch consuming — it stopped the metric from updating at all,
freezing at whatever it last reported before dying rather than climbing.
Redis Streams state has no such restriction (`XINFO GROUPS` works from any
client with Redis access, not just a member of the group), so the fix
consolidates every consumer group's backlog — kitchen's and dispatch's
included — into one place: `front_of_house.observability`, the one service
every chaos scenario keeps alive by construction (PIZZA.md's own
`dispatch_down` expectation is literally "front-of-house and kitchen stay
healthy"). Kitchen's and dispatch's own `observability.py` modules no
longer report `stream_pending` for their own groups at all — a service is
structurally the wrong place to ask "is your own backlog growing," and
having only one reporter also avoids double-counting when both the
(removed) self-report and front-of-house's report would otherwise coexist
while a service is healthy.

Counters and histograms (`orders_placed_total`, `order_cook_seconds`,
`promise_error_seconds`, `slot_claim_contention_total`) are recorded at the
one call site that actually observes the event.

A fourth problem in the same family surfaced afterward, from just looking
at the dashboard: `kitchen_queue_depth` and `oven_slots_occupied` each drew
as five-plus near-identical overlapping lines instead of one, because
`ObservableGauge` registration for both lived in `kitchen/observability.py`
at unconditional module level — imported, and therefore registered, by
every one of kitchen's five OS processes (web, celery worker, relay,
consumer, reaper), each with its own `service.instance.id`. Every process
queries the same Postgres tables and reports the same number, so this
wasn't wrong data, just needless duplication — Prometheus storing five
copies of one fact and Grafana drawing five superimposed lines for it.
Fixed by moving gauge registration out of `configure()` (called by every
process) into a new `register_pull_gauges()`, called only from `main.py` —
the one process a single-instance-per-service laptop demo always keeps
running. `front_of_house.observability`'s `stream_pending` had the identical
bug for the identical reason (registered at module level, front-of-house
runs around ten processes), fixed the same way: moved into `configure_web()`,
called only by the ASGI app. The Grafana queries for both were also changed
to aggregate (`max by (...)`) rather than pass the bare metric through —
defensive, since a *correctly* single-reporter gauge should never need it,
but cheap insurance against the same class of bug recurring, and it also
turned out to matter for a different reason: `slot_claim_contention_total`
is a **counter**, not a gauge, incremented inside kitchen's Celery worker —
whose prefork pool is itself several OS processes, each holding a genuine
*partial* count rather than a duplicate of one total. That panel needed
`sum(rate(...))` regardless of the registration fix, since summing
per-replica counters is simply the correct way to read one, not a
workaround for anything.

### 2. Trace continuity across the event spine needs the envelope, not just auto-instrumentation

Standard OTel instrumentation (Django, FastAPI, httpx) gives automatic W3C
`traceparent` propagation across a synchronous HTTP hop — front-of-house
calling kitchen's `/capacity/quote` connects for free. It does not span
Redis Streams: there is no built-in propagator for "a value written to
Postgres now, read back and republished to Redis 50ms later by an unrelated
process." Without doing something about this, `order.ready`'s five-consumer
fan-out (the showpiece in PIZZA.md) would produce five orphaned traces that
merely share a `correlation_id` string, not the one connected waterfall
Phase 9's own acceptance criterion asks for.

`EventEnvelope` gains one additive field:

```python
trace_context: dict[str, str] | None = None
```

The first version of this injected at the outbox relay's publish call
(`dinner_rush_core.streams.client.publish`) — the obvious "one shared choke
point every service already calls" — and it produced disconnected
single-service traces instead of one waterfall. The relay is a separate,
decoupled process polling the outbox table on its own loop; by the time a
row reaches it, the request or task that originally caused the event has
long since finished, so there is nothing meaningful active in the relay's
own OTel context to inject. The fix moves injection to where a span *is*
still active: each service's own `build_envelope` (`eventing/writer.py`,
`kitchen/writer.py`, `dispatch/writer.py`), called from inside the original
request handler or the consumer span already wrapping a handler's
execution. `publish` became pure transport — it republishes whatever
`trace_context` the envelope already carries, stamping nothing itself.
Extraction happens in each service's consumer loop via a new
`span_from_envelope` context manager, which wraps the handler dispatch and
is itself the active span if that handler goes on to build a *further*
envelope — which is what makes a five-consumer fan-out chain rather than
each hop only ever linking back to the original HTTP request.

One more hop needed the same fix once traced end to end: kitchen's and
dispatch's cook-progression/assignment chains run through Celery
(`advance_ticket.apply_async`, `assign_order.apply_async`), scheduled from
inside a *consumer* process, executed later in a *worker* process.
`opentelemetry-instrumentation-celery` propagates trace context through task
message headers automatically, but only if it's instrumented in both the
process that calls `apply_async` (the producer) and the one that runs the
task (the worker) — instrumenting only the worker, which is where the
obvious "this runs Celery tasks" intuition points, leaves every
producer-side call site silently uninstrumented and the resulting task
starts a disconnected root span. `kitchen.observability.configure` and
`dispatch.observability.configure` — the one function already called by
every process each service runs — instrument Celery unconditionally now,
so every process that might call `apply_async` gets producer-side header
injection whether or not it's the worker.

A third gap surfaced only by actually placing an order and querying Tempo by
`correlation_id`: front-of-house's own root span never linked to anything,
even with the two fixes above in place — `current_trace_context()` inside
`OrderCreateView.post` was reading back an all-zero, `NonRecordingSpan`
context, despite `DjangoInstrumentor().instrument()` running at startup and
a real, exported "POST" span existing for the same request. The cause:
`opentelemetry-instrumentation-django` depends on
`opentelemetry-instrumentation-wsgi` but not
`opentelemetry-instrumentation-asgi` by default, and this service is served
exclusively over ASGI (Channels/Daphne, never Django's WSGI handler). With
only the WSGI half installed, `DjangoInstrumentor` still creates *a* span —
enough to show up in Tempo — but not by wrapping the ASGI request scope, so
it's never attached to the `contextvars` context the actual view executes
in; `trace.get_current_span()` there sees nothing, same as if instrumentation
were entirely absent. Adding `opentelemetry-instrumentation-asgi` as an
explicit dependency (not merely transitive) fixed it: verified by placing a
real order and confirming Tempo returns exactly one trace, rooted at
`POST api/v1/orders`, containing all 116 spans from front-of-house, kitchen
*and* dispatch for that order's full journey — accept, capacity quote,
five-consumer fan-out, the Celery cook-progression chain, and dispatch's
courier-assignment retries. Worth the paragraph: `pip`/`uv` resolving a
package's stated dependencies cleanly is not the same guarantee as that
package actually doing what its name says in *this* deployment mode, and
the only way this surfaced was end-to-end verification against a live
trace backend, not unit tests or a green CI run.

Additive per DECISIONS.md §0004's own versioning
policy — a consumer that predates this field ignores it and gets an
unlinked span instead of an error, never a hard failure. Tracing is
diagnostic; a missing trace context degrades a query, it doesn't drop a
message.

### 3. Grafana Tempo stores traces; it's a disclosed addition beyond CLAUDE.md's stack table

CLAUDE.md §4 names "OpenTelemetry, Prometheus, Grafana" — nothing that
actually stores and renders a trace waterfall, since Prometheus can't.
Tempo is one more lightweight container, pairs natively with Grafana (the
waterfall renders in Grafana's own Explore view against the Tempo
datasource — no second UI to open, keeping the "one screen" constraint
CLAUDE.md §1 sets), and needs no object storage or clustering for a laptop's
worth of trace volume. `observability/tempo.yaml` runs it in single-binary
mode. Two version notes worth recording since both cost real debugging time
building this phase: `grafana/tempo:latest` currently resolves to Tempo v3's
scheduler/worker split, an incompatible config schema for single-binary mode
— pinned to `2.7.1`, the last monolithic-mode release line. And Tempo's own
OTLP receiver defaults to binding `127.0.0.1`, invisible to the
otel-collector container on the same Docker network, until the endpoint is
set to `0.0.0.0` explicitly in `tempo.yaml`.

### 4. The board's two falsifiability metrics ride the existing websocket, not a new endpoint

`stream_pending` and `promise_error_seconds` are the two SPEC.md §7 calls out
by name as making the backpressure/degradation claims falsifiable. Getting
them onto the board could have meant a new REST endpoint the frontend polls,
or the browser querying Prometheus's HTTP API directly. Both were rejected:
a poll endpoint duplicates plumbing the board already has, and a
browser-to-Prometheus fetch needs Prometheus's port exposed to the host and
CORS configured for no real benefit. Instead, a new Celery beat task
(`front_of_house.eventing.tasks.push_board_metrics`, `celery-worker` now runs
with `-B` rather than a dedicated beat container for one 5-second tick)
queries Prometheus's HTTP API server-side and broadcasts through the same
Channels group `handlers.handle_board_fanout` already uses, as one new
websocket message type (`board.metrics`) the frontend discriminates by a
`type` field domain events never carry. `StatusBar` gains two new optional
props fed by it; the existing client-computed `ordersPerMinute`/
`p95LatePercent` tiles stay exactly as ADR 0008 §6 left them — real,
honestly-labelled approximations, not replaced, since they answer a
different, still-useful question ("what has this browser tab seen in the
last minute") than the Prometheus-backed histogram does.

### 5. The load test sets SPEED itself and ramps past configured capacity on purpose

`scripts/load/rush.js` authenticates as `manager` first and calls the same
`POST /admin/speed` the board's own speed control uses, setting `SPEED=60`
before the run — otherwise a k6 run would need to run for as long as a real
dinner rush to see a single order finish baking. It then ramps orders/minute
(k6's `ramping-arrival-rate` executor, rate expressed as orders/minute
directly) from a calm baseline up past `config.example.yaml`'s
`kitchen.capacity.max_queue_depth`, deliberately, so one run produces both a
throughput number and a genuine rejection rate rather than needing two
separate artifacts to back the "handles load" and "refuses cleanly at
capacity" claims separately. `handleSummary` writes a small, hand-picked
`docs/load/latest.json` rather than k6's full metrics dump, so the number a
README quotes is the one visible in the file, not one a reader has to dig
for.

## Consequences

- `SPEC.md` §7's `oven_slots_occupied` / `oven_slots_total` are one
  `ObservableGauge` (`oven_slots_occupied`) with a `state=occupied|total`
  label, not two separately-named metrics — simpler PromQL (a ratio is one
  metric, not two joined) at the cost of matching the table's literal
  naming. Same trade for `slot_claim_contention_total`: it counts every
  `claim_slot` call that returns `None`, which conflates "lost the `SKIP
  LOCKED` race" with "the oven is genuinely full" — the SQL genuinely can't
  tell the two apart, and for a dashboard the signal that matters is that it
  climbs exactly when the oven is contended, not which of the two happened.
- Running `pytest` without a live `otel-collector` (true for local `make
  test` and CI's `python` job alike, both deliberately scoped to just
  Postgres/Redis) logs background `BatchSpanProcessor` export-retry
  warnings to stderr. Cosmetic, not a failure — the same "tracing is
  diagnostic, never load-bearing" principle as `span_from_envelope`'s
  graceful fallback in decision 2. Not worth adding a fifth CI service
  container to silence.
- Four new containers (`otel-collector`, `tempo`, `prometheus`, `grafana`)
  join `docker compose up`'s default set — `make up`'s "every container
  healthy in under 90s" promise (CLAUDE.md §6) now covers eight more
  processes than Phase 8 left it with, on top of the two already-larger
  ports surface (`otel-collector:4317`, `tempo:3200` exposed to the host
  purely for debugging convenience, matching `prometheus:9090`/
  `grafana:3000`'s existing exposure).
