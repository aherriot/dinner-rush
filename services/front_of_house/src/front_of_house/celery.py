"""The Celery app — scheduled/delayed work only (DECISIONS.md §0003's
three-jobs table). Domain events fan out over Redis Streams, not Celery;
Celery's whole job here is countdown-scheduling the next cook-progression
step with `apply_async(countdown=...)`.
"""

import os

from celery import Celery
from celery.signals import worker_process_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "front_of_house.settings")

app = Celery("front_of_house")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_process_init.connect
def _configure_otel_in_forked_worker(**_kwargs: object) -> None:
    """Must run after fork, not at import time: the prefork pool (this
    worker's default) forks *after* this module's top level runs, and
    `BatchSpanProcessor`'s background export thread doesn't survive a fork
    — every child would inherit a parent thread that's no longer running.
    `worker_process_init` fires once per forked child, same reasoning as
    kitchen's own `_dispose_engine_in_forked_worker`."""
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    from front_of_house.observability import configure

    configure()
    CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]
    HTTPXClientInstrumentor().instrument()  # push_board_metrics polls Prometheus's HTTP API
