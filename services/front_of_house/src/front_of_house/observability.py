"""OTel bootstrap and domain metrics for front-of-house (SPEC.md §7, ADR 0009).

`configure()` is the plain bootstrap, called once by every process this
service runs (the ASGI app, the Celery worker, the relay, each stream
consumer). `configure_web()` additionally instruments Django's request
cycle and outbound httpx calls, which is what makes the synchronous half of
a trace — front-of-house calling kitchen's `/capacity/quote` — connect
automatically; the async half (the event spine) is wired separately in
`dinner_rush_core.streams`. It's also the only place `stream_pending` gets
registered: front-of-house runs around ten OS processes (web, celery
worker, relay, seven stream consumers), and this is a pull-based gauge that
reads the same Redis state regardless of which process asks — registering
it everywhere doesn't make the number more correct, it just makes
Prometheus store ten near-identical time series that Grafana draws as ten
overlapping lines instead of one. Caught live, by looking at the dashboard
and counting lines, not by a test.
"""

from collections.abc import Iterable

from opentelemetry.metrics import CallbackOptions, Observation

from dinner_rush_core.config import load_config
from dinner_rush_core.observability import get_meter, setup_otel

SERVICE_NAME = "front-of-house"

# Every (stream, consumer group) pair across all three services — not just
# the ones front-of-house itself consumes. This is deliberate, not scope
# creep: `stream_pending` is only useful for the one demo it exists for
# (`docker compose stop dispatch`, PHASES.md Phase 10) if it keeps updating
# while the service that OWNS the group is dead. Redis Streams state is
# global — any client can XINFO GROUPS any group — so having kitchen and
# dispatch each self-report only their own group means the exact scenario
# that matters (that service being down) is the one where the metric goes
# stale instead of climbing. Front-of-house never appears in any chaos
# scenario as the thing being killed (PIZZA.md: "front-of-house and kitchen
# stay healthy" is the assertion `dispatch_down` makes), so it's the one
# reliable place to read every group's backlog from. Kitchen and dispatch's
# own `observability.py` modules don't duplicate this.
_STREAM_PENDING_TARGETS = [
    ("events:order", "cg:analytics"),
    ("events:order", "cg:ws-fanout"),
    ("events:order", "cg:order-sync"),
    ("events:courier", "cg:order-sync"),
    ("events:order", "cg:ws-board-fanout"),
    ("events:oven", "cg:ws-board-fanout"),
    ("events:courier", "cg:ws-board-fanout"),
    ("events:order", "cg:kitchen"),
    ("events:order", "cg:dispatch"),
]

_configured_web = False


def configure() -> None:
    setup_otel(SERVICE_NAME, load_config().observability)


def configure_web() -> None:
    global _configured_web
    if _configured_web:
        return
    _configured_web = True

    configure()

    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    DjangoInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    _meter.create_observable_gauge(
        "stream_pending",
        callbacks=[_stream_pending_callback],
        description="pending+lag per (stream, consumer group) — the backlog a chaos demo drains",
    )


_meter = get_meter(SERVICE_NAME)

orders_placed_total = _meter.create_counter(
    "orders_placed_total", description="Orders placed, by outcome"
)
order_rejections_total = _meter.create_counter(
    "order_rejections_total", description="Orders rejected, by reason"
)
promise_error_seconds = _meter.create_histogram(
    "promise_error_seconds",
    unit="s",
    description="delivered_at minus promised_at — p50/p95 promise accuracy",
)


def _stream_pending_callback(_options: CallbackOptions) -> Iterable[Observation]:
    """Pull-based on purpose: queried live at each collection tick rather
    than tracked with manual increment/decrement bookkeeping, so this is
    correct regardless of which process actually advanced the backlog —
    the whole point of a gauge over a counter here."""
    from dinner_rush_core.streams import backlog
    from front_of_house.eventing.redis_client import get_redis_client

    client = get_redis_client()
    for stream, group in _STREAM_PENDING_TARGETS:
        try:
            count = backlog(client, stream, group)
        except Exception:
            continue
        yield Observation(count, {"stream": stream, "group": group})
