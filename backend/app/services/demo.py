from sqlalchemy.orm import Session

from app.enums import LotStatus
from app.models import Lot
from app.services.host_prep import prepare_line
from app.services.line_runner import run_work_order
from app.services.work_orders import create_and_release


def run_demo(
    db: Session,
    *,
    product_type: str,
    recipe_id: str,
    inspect_result: str,
) -> dict:
    prepare_line(db, recipe_id)
    order, panel_ids = create_and_release(
        db,
        product_type=product_type,
        recipe_id=recipe_id,
        qty=1,
    )
    ran = run_work_order(db, order.id, inspect_result=inspect_result)
    lot = db.get(Lot, order.lot_id)
    held_fail = (
        inspect_result == "FAIL"
        and lot is not None
        and lot.status == LotStatus.HOLD.value
        and lot.hold_reason == "INSPECT_FAIL"
    )
    return {
        "ok": bool(ran.get("ok") or held_fail),
        "seed_used": False,
        "work_order_id": order.id,
        "lot_id": order.lot_id,
        "cassette_id": order.cassette_id,
        "panel_ids": panel_ids,
        "inspect_result": inspect_result,
        "lot_status": lot.status if lot else None,
        "hold_reason": lot.hold_reason if lot else None,
        "run": ran,
    }
