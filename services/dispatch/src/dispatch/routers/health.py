from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from dispatch.db import get_session
from dispatch.redis_client import get_redis_client

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: the process is up and can serve a response."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(response: Response, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Readiness: dispatch's own dependencies are actually reachable."""
    checks: dict[str, str] = {}
    ready = True

    try:
        session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"
        ready = False

    try:
        get_redis_client().ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        ready = False

    response.status_code = 200 if ready else 503
    return {"status": "ready" if ready else "not-ready", "checks": checks}
