"""OTel bootstrap and domain metrics for kitchen (SPEC.md §7, ADR 0009).

`configure()` is the plain bootstrap; `main.py` additionally instruments
the FastAPI app and outbound httpx (JWKS fetch) so the synchronous half of
a trace connects automatically. The gauges here are all pull-based
(`ObservableGauge` callbacks that query Postgres directly at each collection
tick) rather than manually incremented/decremented — kitchen runs several
OS processes (web, celery worker, relay, consumer, reaper) and a gauge that
reflects live external state is naturally correct regardless of which
process last touched it, unlike a counter.

Kitchen does *not* report its own `stream_pending{group="cg:kitchen"}` —
`front_of_house.observability` reports every consumer group across all
three services, on purpose: a service reporting only its own backlog stops
updating the moment that service is the one that's down, which is exactly
the scenario the metric exists to show (see that module's docstring).
"""

from collections.abc import Iterable

from opentelemetry.metrics import CallbackOptions, Observation
from sqlalchemy import func, select

from dinner_rush_core.config import load_config
from dinner_rush_core.observability import get_meter, setup_otel

SERVICE_NAME = "kitchen"

_configured = False


def configure() -> None:
    """Called by every kitchen process — the web app, the relay, the
    consumer, the reaper, and (post-fork, via `celery_app.py`'s own
    `worker_process_init` hook) the Celery worker.

    Includes `CeleryInstrumentor` here, not just in the worker: kitchen's
    consumer and reaper processes are Celery *producers* too (`start_
    progression`/`reconcile.py` call `advance_ticket.apply_async`) — without
    producer-side instrumentation active in *those* processes, no trace
    headers ever reach the task message, and the worker executing it starts
    a disconnected root span instead of a child of the span that scheduled
    it. Every process that might call `apply_async` needs this, not only
    the one that runs the resulting task."""
    global _configured
    if _configured:
        return
    _configured = True
    setup_otel(SERVICE_NAME, load_config().observability)

    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]


_meter = get_meter(SERVICE_NAME)

order_cook_seconds = _meter.create_histogram(
    "order_cook_seconds", unit="s", description="Actual bake duration, started_at to boxed"
)
slot_claim_contention_total = _meter.create_counter(
    "slot_claim_contention_total",
    description=(
        "Claim attempts that didn't win a slot. SKIP LOCKED doesn't distinguish "
        "'lost a race' from 'genuinely no free slot' at the SQL level, so this "
        "counts both — the signal that matters for a demo is that it climbs "
        "exactly when the oven is being contended for."
    ),
)


def _oven_occupancy_callback(_options: CallbackOptions) -> Iterable[Observation]:
    from kitchen.db import SessionLocal
    from kitchen.models import OvenSlot

    session = SessionLocal()
    try:
        occupied = session.execute(
            select(func.count()).select_from(OvenSlot).where(OvenSlot.order_id.is_not(None))
        ).scalar_one()
        total = session.execute(select(func.count()).select_from(OvenSlot)).scalar_one()
    finally:
        session.close()
    yield Observation(occupied, {"state": "occupied"})
    yield Observation(total, {"state": "total"})


def _queue_depth_callback(_options: CallbackOptions) -> Iterable[Observation]:
    from kitchen.db import SessionLocal
    from kitchen.models import Ticket

    session = SessionLocal()
    try:
        depth = session.execute(
            select(func.count()).select_from(Ticket).where(Ticket.status != "ready")
        ).scalar_one()
    finally:
        session.close()
    yield Observation(depth)


_meter.create_observable_gauge(
    "oven_slots_occupied",
    callbacks=[_oven_occupancy_callback],
    description="oven_slot rows by occupancy state — filter on state=occupied/total",
)
_meter.create_observable_gauge(
    "kitchen_queue_depth",
    callbacks=[_queue_depth_callback],
    description="Tickets not yet ready — the number that climbs during a rush",
)
