"""The event envelope every domain event travels in (DECISIONS.md §0004).

Every producer wraps its payload in this shape before it ever reaches an
outbox row or a stream entry. `sequence` is a per-aggregate monotonic
counter — it lets a consumer notice it has already seen a *later* event and
drop a stale redelivery, which is out-of-order protection layered on top of
plain deduplication. `correlation_id` and `causation_id` together let the
full fan-out tree of one order be reconstructed later (Phase 9's trace
waterfall). `trace_context` carries the W3C traceparent/tracestate across
the one hop OTel's own instrumentation can't see automatically — the
publish-to-stream/consume-from-stream boundary — so a trace stays connected
across the async fan-out, not just the synchronous HTTP calls. Additive per
the versioning policy below; older consumers ignore it.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EventEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID
    event_type: str
    event_version: int
    occurred_at: datetime
    aggregate_type: str
    aggregate_id: UUID
    sequence: int
    correlation_id: UUID
    causation_id: UUID | None = None
    producer: str
    payload: dict[str, Any]
    trace_context: dict[str, str] | None = None
