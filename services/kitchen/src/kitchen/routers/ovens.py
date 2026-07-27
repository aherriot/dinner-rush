from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from kitchen.api_models import OvenOut
from kitchen.db import get_session
from kitchen.models import Oven

router = APIRouter()


@router.get("/ovens", response_model=list[OvenOut])
def get_ovens(session: Session = Depends(get_session)) -> list[Oven]:
    """`GET /ovens` (SPEC.md §3.3) — slot occupancy + `frees_at`."""
    stmt = select(Oven).options(selectinload(Oven.slots))
    return list(session.execute(stmt).scalars().all())
