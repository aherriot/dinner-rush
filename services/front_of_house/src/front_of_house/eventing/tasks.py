"""Periodic push of the two falsifiability metrics onto the board (Phase 9).

`stream_pending` and `promise_error_seconds` (SPEC.md §7) live in
Prometheus, not in any one service's own process — they're aggregated from
every consumer group across all three services. Getting them onto the
board means polling Prometheus's HTTP API rather than reading local state,
then broadcasting over the same Channels group `handlers.handle_board_fanout`
already uses, so the frontend needs one new websocket message type rather
than a second connection or a REST poll.
"""

import httpx
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer

PROMETHEUS_URL = "http://prometheus:9090"
BOARD_GROUP = "board"


def _query_scalar(promql: str) -> float | None:
    try:
        response = httpx.get(
            f"{PROMETHEUS_URL}/api/v1/query", params={"query": promql}, timeout=3.0
        )
        response.raise_for_status()
        result = response.json()["data"]["result"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    if not result:
        return None
    return float(result[0]["value"][1])


@shared_task(ignore_result=True)
def push_board_metrics() -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    stream_pending = _query_scalar("sum(stream_pending)")
    promise_error_p95_seconds = _query_scalar(
        "histogram_quantile(0.95, sum(rate(promise_error_seconds_bucket[5m])) by (le))"
    )
    async_to_sync(channel_layer.group_send)(
        BOARD_GROUP,
        {
            "type": "board.metrics",
            "stream_pending": stream_pending,
            "promise_error_p95_seconds": promise_error_p95_seconds,
        },
    )
