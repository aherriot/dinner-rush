from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


def problem_detail_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """RFC 7807 `application/problem+json` for every DRF error response."""
    response = exception_handler(exc, context)
    if response is None:
        return None

    request = context["request"]
    detail = response.data.get("detail") if isinstance(response.data, dict) else response.data

    response.data = {
        "type": "about:blank",
        "title": exc.__class__.__name__,
        "status": response.status_code,
        "detail": str(detail) if detail is not None else str(exc),
        "instance": request.path,
        "correlation_id": getattr(request, "correlation_id", None),
    }
    response["Content-Type"] = "application/problem+json"
    return response
