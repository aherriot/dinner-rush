from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dinner_rush_core.config import load_config
from kitchen import capacity
from kitchen.api_models import CapacityQuoteRequest, CapacityQuoteResponse
from kitchen.auth import require_service_scope
from kitchen.db import get_session

router = APIRouter(dependencies=[Depends(require_service_scope("kitchen:call"))])


@router.post("/capacity/quote", response_model=CapacityQuoteResponse)
def post_capacity_quote(
    request: CapacityQuoteRequest, session: Session = Depends(get_session)
) -> CapacityQuoteResponse:
    config = load_config()
    menu_by_sku = {item.sku: item for item in config.menu}
    missing = [line.sku for line in request.items if line.sku not in menu_by_sku]
    if missing:
        raise HTTPException(status_code=422, detail=f"unknown menu item sku(s): {missing}")

    result = capacity.quote(
        session,
        items=[(line.sku, line.qty) for line in request.items],
        menu_by_sku=menu_by_sku,
        capacity=config.kitchen.capacity,
    )
    return CapacityQuoteResponse(
        can_accept=result.can_accept,
        queue_depth=result.queue_depth,
        projected_wait_s=result.projected_wait_s,
    )
