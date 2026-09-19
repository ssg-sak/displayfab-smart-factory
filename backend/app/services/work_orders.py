from __future__ import annotations

from sqlalchemy.orm import Session

from app.enums import LotStatus, PanelStatus, ProductType, WorkOrderStatus
from app.models import Lot, Panel, Recipe, WorkOrder
from app.services.event_bus import publish
from app.services.timeutil import utcnow


class WorkOrderError(ValueError):
    pass


def _next_seq(values: list[str], prefix: str) -> int:
    nums = []
    for raw in values:
        if not raw.startswith(prefix):
            continue
        tail = raw[len(prefix) :]
        if tail.isdigit():
            nums.append(int(tail))
    return (max(nums) if nums else 0) + 1


def _padded(prefix: str, n: int, width: int) -> str:
    return f"{prefix}{n:0{width}d}"


def create_and_release(
    db: Session,
    *,
    product_type: str,
    recipe_id: str | None,
    qty: int,
) -> tuple[WorkOrder, list[str]]:
    product = product_type.upper()
    if product not in (ProductType.OLED.value, ProductType.LCD.value):
        raise WorkOrderError("product_type은 OLED 또는 LCD")

    if not recipe_id:
        recipe_id = "RCP-OLED-A01" if product == ProductType.OLED.value else "RCP-LCD-C01"

    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise WorkOrderError(f"Recipe 없음: {recipe_id}")
    if recipe.product_type != product:
        raise WorkOrderError(f"{product} 지시인데 Recipe는 {recipe.product_type}")

    now = utcnow()
    day = now.strftime("%Y%m%d")
    wo_prefix = f"WO-{day}-"
    lot_prefix = f"LOT-{day}-"
    cst_prefix = f"CST-{product}-"

    wo_n = _next_seq([row.id for row in db.query(WorkOrder).all()], wo_prefix)
    lot_n = _next_seq([row.id for row in db.query(Lot).all()], lot_prefix)
    cst_n = _next_seq([row.cassette_id for row in db.query(Lot).all()], cst_prefix)
    panel_n = _next_seq([row.id for row in db.query(Panel).all()], "PNL-")

    wo_id = _padded(wo_prefix, wo_n, 3)
    lot_id = _padded(lot_prefix, lot_n, 3)
    cassette_id = _padded(cst_prefix, cst_n, 3)
    panel_ids = [_padded("PNL-", panel_n + i, 5) for i in range(qty)]

    lot = Lot(
        id=lot_id,
        cassette_id=cassette_id,
        product_type=product,
        expected_recipe_id=recipe_id,
        status=LotStatus.WAIT.value,
    )
    db.add(lot)
    for slot, panel_id in enumerate(panel_ids, start=1):
        db.add(
            Panel(
                id=panel_id,
                lot_id=lot_id,
                slot_no=slot,
                status=PanelStatus.WAIT.value,
            )
        )

    order = WorkOrder(
        id=wo_id,
        product_type=product,
        recipe_id=recipe_id,
        qty=qty,
        status=WorkOrderStatus.RELEASED.value,
        lot_id=lot_id,
        cassette_id=cassette_id,
        created_at=now,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    publish(
        {
            "type": "work_order",
            "id": order.id,
            "lot_id": lot_id,
            "product_type": product,
            "qty": qty,
        }
    )
    return order, panel_ids


def panel_counts(db: Session, lot_id: str | None) -> tuple[int, int, int]:
    if not lot_id:
        return 0, 0, 0
    panels = db.query(Panel).filter(Panel.lot_id == lot_id).all()
    complete = sum(1 for p in panels if p.status == PanelStatus.COMPLETE.value)
    fail = sum(1 for p in panels if p.status == PanelStatus.FAIL.value)
    scrap = sum(1 for p in panels if p.status == PanelStatus.SCRAP.value)
    return complete, fail, scrap


def refresh_work_order_for_lot(db: Session, lot_id: str | None) -> None:
    if not lot_id:
        return
    order = db.query(WorkOrder).filter(WorkOrder.lot_id == lot_id).first()
    if order is None:
        return
    panels = db.query(Panel).filter(Panel.lot_id == lot_id).all()
    if not panels:
        return
    finished = {PanelStatus.COMPLETE.value, PanelStatus.SCRAP.value}
    if all(p.status in finished for p in panels):
        order.status = WorkOrderStatus.DONE.value


def list_work_orders(db: Session) -> list[tuple[WorkOrder, list[str]]]:
    rows = db.query(WorkOrder).order_by(WorkOrder.created_at.desc()).all()
    out = []
    for order in rows:
        panels = []
        if order.lot_id:
            panels = [
                p.id
                for p in db.query(Panel)
                .filter(Panel.lot_id == order.lot_id)
                .order_by(Panel.slot_no.asc())
                .all()
            ]
        out.append((order, panels))
    return out
