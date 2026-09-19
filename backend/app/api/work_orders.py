from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import WorkOrderIn, WorkOrderOut
from app.services.work_orders import WorkOrderError, create_and_release, list_work_orders, panel_counts

router = APIRouter(prefix="/work-orders", tags=["work-orders"])


def _to_out(db, order, panel_ids: list[str]) -> WorkOrderOut:
    complete, fail, scrap = panel_counts(db, order.lot_id)
    return WorkOrderOut(
        id=order.id,
        product_type=order.product_type,
        recipe_id=order.recipe_id,
        qty=order.qty,
        status=order.status,
        lot_id=order.lot_id,
        cassette_id=order.cassette_id,
        panel_ids=panel_ids,
        complete=complete,
        fail=fail,
        scrap=scrap,
        created_at=order.created_at,
    )


@router.get("", response_model=list[WorkOrderOut])
def get_work_orders(db: Session = Depends(get_db)) -> list[WorkOrderOut]:
    return [_to_out(db, order, panels) for order, panels in list_work_orders(db)]


@router.post("", response_model=WorkOrderOut)
def post_work_order(payload: WorkOrderIn, db: Session = Depends(get_db)) -> WorkOrderOut:
    try:
        order, panels = create_and_release(
            db,
            product_type=payload.product_type,
            recipe_id=payload.recipe_id,
            qty=payload.qty,
        )
    except WorkOrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_out(db, order, panels)
