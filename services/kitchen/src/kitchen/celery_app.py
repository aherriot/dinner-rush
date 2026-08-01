"""Scheduled/delayed work only (DECISIONS.md §0003) — the cook-progression
countdown chain, same division of labour as front-of-house's Celery app.
"""

from celery import Celery
from celery.signals import worker_process_init

from kitchen import settings

app = Celery("kitchen", broker=settings.CELERY_BROKER_URL)
app.conf.task_default_queue = "kitchen"
app.autodiscover_tasks(["kitchen"])


@worker_process_init.connect
def _dispose_engine_in_forked_worker(**_kwargs: object) -> None:
    """The prefork pool forks worker processes *after* `kitchen.db.engine`
    is created — without this, each child inherits the parent's pooled
    connections and sharing a live socket across processes hangs or
    corrupts the protocol. `dispose()` drops the inherited pool so each
    child opens its own connections on first use."""
    from kitchen.db import engine

    engine.dispose()


@worker_process_init.connect
def _configure_otel_in_forked_worker(**_kwargs: object) -> None:
    """Same fork hazard as above, for a different resource: `BatchSpanProcessor`'s
    background export thread doesn't survive a fork, so OTel setup has to
    happen after the prefork pool forks each child, not at import time.
    `configure()` also instruments Celery itself (both producer and
    consumer side) — see its own docstring."""
    from kitchen.observability import configure

    configure()
