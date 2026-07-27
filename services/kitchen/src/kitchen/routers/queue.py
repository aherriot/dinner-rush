from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from kitchen.api_models import TicketOut
from kitchen.auth import require_service_scope
from kitchen.db import get_session
from kitchen.models import Ticket

router = APIRouter(dependencies=[Depends(require_service_scope("kitchen:read"))])


@router.get("/queue", response_model=list[TicketOut])
def get_queue(session: Session = Depends(get_session)) -> list[Ticket]:
    """`GET /queue` (SPEC.md §3.3) — tickets ordered by priority."""
    stmt = (
        select(Ticket)
        .where(Ticket.status != "ready")
        .order_by(Ticket.priority.desc(), Ticket.queued_at)
    )
    return list(session.execute(stmt).scalars().all())
