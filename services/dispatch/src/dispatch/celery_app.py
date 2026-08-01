"""Scheduled/delayed work only (DECISIONS.md §0003) — assignment retry and
the courier motion autopilot (ADR 0007 §6), same division of labour as
front-of-house's and kitchen's Celery apps.
"""

from celery import Celery
from celery.signals import worker_process_init

from dispatch import settings

app = Celery("dispatch", broker=settings.CELERY_BROKER_URL)
app.conf.task_default_queue = "dispatch"
app.autodiscover_tasks(["dispatch"])


@worker_process_init.connect
def _dispose_engine_in_forked_worker(**_kwargs: object) -> None:
    """Same fix as kitchen's — the prefork pool forks *after*
    `dispatch.db.engine` is created, so each child must drop the inherited
    connection pool rather than share live sockets across processes."""
    from dispatch.db import engine

    engine.dispose()


@worker_process_init.connect
def _configure_otel_in_forked_worker(**_kwargs: object) -> None:
    """Same fork hazard as above, for `BatchSpanProcessor`'s background
    export thread — see kitchen's identical hook for the full reasoning.
    `configure()` also instruments Celery itself (both producer and
    consumer side) — see its own docstring."""
    from dispatch.observability import configure

    configure()
