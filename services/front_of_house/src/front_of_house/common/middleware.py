from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from dinner_rush_core.ids import uuid7

CORRELATION_ID_HEADER = "X-Correlation-Id"


class CorrelationIdMiddleware:
    """Every request gets a correlation_id — echoed if the caller sent one.

    Threaded through RFC 7807 error bodies (common.exceptions) and, from
    Phase 3 onward, the event envelope.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid7())
        request.correlation_id = correlation_id  # type: ignore[attr-defined]
        response = self.get_response(request)
        response[CORRELATION_ID_HEADER] = correlation_id
        return response
