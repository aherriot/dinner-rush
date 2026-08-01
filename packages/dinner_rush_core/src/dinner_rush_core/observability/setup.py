"""`setup_otel` — the one-call OTel bootstrap every process runs at startup.

Idempotent per process: Django's autoreloader and Celery's worker bootstrap
both re-execute module-level code in ways that could otherwise register the
same exporter twice and double-export every span. A module-level guard
makes a second call a no-op rather than a footgun.
"""

import logging

from opentelemetry import metrics, propagate, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import Meter, MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Tracer, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from dinner_rush_core.config import ObservabilityConfig

_log = logging.getLogger(__name__)
_configured_service: str | None = None


def setup_otel(service_name: str, config: ObservabilityConfig) -> None:
    """Wires OTLP export for both traces and metrics for this process.

    `service_name` becomes the `service.name` resource attribute — the
    label every span and metric carries into Tempo/Prometheus/Grafana, and
    the thing that makes a query like "every span in this trace, grouped by
    service" possible in the first place.
    """
    global _configured_service
    if _configured_service is not None:
        if _configured_service != service_name:
            _log.warning(
                "setup_otel already configured for %s; ignoring re-configure as %s",
                _configured_service,
                service_name,
            )
        return
    _configured_service = service_name

    resource = Resource.create({"service.name": service_name})

    tracer_provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(config.trace_sample_ratio)),
    )
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=config.otel_endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=config.otel_endpoint, insecure=True)
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    _log.info(
        "otel configured: service=%s endpoint=%s sample_ratio=%s",
        service_name,
        config.otel_endpoint,
        config.trace_sample_ratio,
    )


def get_tracer(name: str) -> Tracer:
    return trace.get_tracer(name)  # type: ignore[return-value]


def get_meter(name: str) -> Meter:
    return metrics.get_meter(name)  # type: ignore[return-value]


def current_trace_context() -> dict[str, str] | None:
    """Captures the *currently active* span's W3C context, to stash on an
    envelope at the moment it's built — not at publish time. The outbox
    relay runs in its own process on its own polling loop, decoupled from
    whatever request or task originally caused the event; by the time it
    calls `streams.publish`, there is no meaningful span active to inject.
    The request/task span *is* active here, inside `build_envelope`, which
    is why this belongs there instead."""
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier or None
