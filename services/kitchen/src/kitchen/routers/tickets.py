import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from kitchen.api_models import TicketAdvanceRequest, TicketOut
from kitchen.auth import require_service_scope
from kitchen.db import get_session
from kitchen.fsm import IllegalTransition, apply_transition
from kitchen.models import Ticket

router = APIRouter(dependencies=[Depends(require_service_scope("kitchen:advance"))])


@router.post("/tickets/{ticket_id}/advance", response_model=TicketOut)
def advance_ticket_manually(
    ticket_id: uuid.UUID, request: TicketAdvanceRequest, session: Session = Depends(get_session)
) -> Ticket:
    """Manual override — manager/kitchen only (SPEC.md §3.3).

    Board calling this directly with a staff token is a Phase 8 concern (see
    `kitchen.auth`'s module docstring); until then it's reached only through
    front-of-house's own service token, scoped to `kitchen:advance`.
    """
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    try:
        ticket.status = apply_transition(ticket.status, request.event)
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return ticket
