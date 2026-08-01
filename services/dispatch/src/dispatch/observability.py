"""OTel bootstrap for dispatch (SPEC.md §7, ADR 0009).

Dispatch owns no metric in SPEC.md's table of its own —
`stream_pending{group="cg:dispatch"}` is reported by
`front_of_house.observability` instead, deliberately: a service reporting
only its own consumer group's backlog stops updating the moment that
service is the one that's down, which is exactly the
`docker compose stop dispatch` chaos demo (PHASES.md Phase 10) this metric
exists to show. See `front_of_house.observability`'s docstring.
"""

from dinner_rush_core.config import load_config
from dinner_rush_core.observability import get_meter, setup_otel

SERVICE_NAME = "dispatch"

_configured = False


def configure() -> None:
    """Called by every dispatch process. Includes `CeleryInstrumentor` here,
    not just in the worker — dispatch's consumer is a Celery *producer* too
    (`assign_order.apply_async` on `order.ready`), and without producer-side
    instrumentation active in that process, no trace headers reach the task
    message. See `kitchen.observability.configure`'s identical reasoning."""
    global _configured
    if _configured:
        return
    _configured = True
    setup_otel(SERVICE_NAME, load_config().observability)

    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]


_meter = get_meter(SERVICE_NAME)  # reserved for a future dispatch-specific metric
