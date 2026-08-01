"""OpenTelemetry bootstrap, shared by every process in every service (ADR 0009).

One function, `setup_otel`, called once per process — the web app, each
Celery worker, the outbox relay, each stream consumer, the kitchen reaper —
the same way `dinner_rush_core.config.load_config` already is. It wires both
traces and metrics through a single OTLP endpoint (the `otel-collector`
container in compose.yaml), because this project runs many OS processes per
logical service and a raw `prometheus_client` registry doesn't share state
across them without file-based multiprocess mode. Routing everything through
one collector sidesteps that entirely.
"""

from dinner_rush_core.observability.setup import (
    current_trace_context,
    get_meter,
    get_tracer,
    setup_otel,
)

__all__ = ["current_trace_context", "get_meter", "get_tracer", "setup_otel"]
