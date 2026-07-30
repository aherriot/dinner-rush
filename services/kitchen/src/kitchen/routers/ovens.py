import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from kitchen.api_models import OvenOut, OvenStatusUpdateRequest
from kitchen.auth import require_service_scope
from kitchen.db import get_session
from kitchen.models import Oven
from kitchen.writer import build_envelope, write_outbox_event

router = APIRouter(dependencies=[Depends(require_service_scope("kitchen:read"))])
admin_router = APIRouter(dependencies=[Depends(require_service_scope("kitchen:advance"))])

VALID_OVEN_STATUSES = {"available", "down"}


@router.get("/ovens", response_model=list[OvenOut])
def get_ovens(session: Session = Depends(get_session)) -> list[Oven]:
    """`GET /ovens` (SPEC.md §3.3) — slot occupancy + `frees_at`."""
    stmt = select(Oven).options(selectinload(Oven.slots))
    return list(session.execute(stmt).scalars().all())


@admin_router.post("/ovens/{oven_id}/status", response_model=OvenOut)
def set_oven_status(
    oven_id: uuid.UUID,
    request: OvenStatusUpdateRequest,
    session: Session = Depends(get_session),
) -> Oven:
    """`POST /admin/ovens/{id}/status` (SPEC.md §3.2), reached via front-of-house's
    proxy — the chaos "oven down" scenario's write path.

    Emits `oven.down`/`oven.restored` (SPEC.md §4) through kitchen's own
    outbox in the same transaction as the status flip, so the board's oven
    grid repaints from the same event spine as everything else rather than
    from a side-channel poll. A repeated call with the status unchanged is a
    no-op — it does not re-emit, since that would be a duplicate state
    transition rather than a genuine one.
    """
    if request.status not in VALID_OVEN_STATUSES:
        raise HTTPException(
            status_code=422, detail=f"status must be one of {sorted(VALID_OVEN_STATUSES)}"
        )
    oven = session.get(Oven, oven_id)
    if oven is None:
        raise HTTPException(status_code=404, detail="oven not found")

    if oven.status == request.status:
        return oven

    oven.status = request.status
    oven.event_sequence += 1
    event_type = "oven.down" if request.status == "down" else "oven.restored"
    envelope = build_envelope(
        event_type=event_type,
        aggregate_type="oven",
        aggregate_id=oven.id,
        sequence=oven.event_sequence,
        correlation_id=oven.id,
        payload={"oven_id": str(oven.id), "slot_count": oven.slot_count},
    )
    write_outbox_event(session, envelope)
    session.commit()
    session.refresh(oven)
    return oven
