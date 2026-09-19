from sqlalchemy.orm import Session

from app.domain.rules import route_for
from app.enums import ConnectionStatus, LotStatus, PanelStatus
from app.models import Equipment, Lot, Panel, ProcessEvent
from app.schemas import (
    MesBoardOut,
    MesEquipmentOut,
    MesLotOut,
    MesOrderOut,
    MesStepOut,
)
from app.services.dispatch import lot_dispatch
from app.services.production import today_production
from app.services.timeutil import utcnow
from app.services.work_orders import list_work_orders, panel_counts


NOTE = "오늘 지시 · 재공 · 설비 · 품질. 스마트팩토리 생산 화면."


def _step_done(db: Session, panel_id: str, step: str) -> bool:
    row = (
        db.query(ProcessEvent.id)
        .filter(ProcessEvent.panel_id == panel_id, ProcessEvent.process_step == step)
        .first()
    )
    return row is not None


def lot_route_progress(db: Session, lot: Lot) -> MesLotOut:
    route = route_for(lot.product_type)
    panels = db.query(Panel).filter(Panel.lot_id == lot.id).order_by(Panel.slot_no.asc()).all()
    total = len(panels)
    steps = []
    for step in route:
        done = sum(1 for panel in panels if _step_done(db, panel.id, step))
        if lot.status == LotStatus.HOLD.value and lot.current_step == step:
            state = "hold"
        elif done >= total and total:
            state = "done"
        elif done > 0 or lot.current_step == step:
            state = "now"
        else:
            state = "wait"
        steps.append(MesStepOut(step=step, done=done, total=total, state=state))

    nxt = lot_dispatch(db, lot) if panels else None
    complete, fail, scrap = panel_counts(db, lot.id)
    return MesLotOut(
        lot_id=lot.id,
        cassette_id=lot.cassette_id,
        product_type=lot.product_type,
        recipe_id=lot.expected_recipe_id,
        status=lot.status,
        hold_reason=lot.hold_reason,
        current_step=lot.current_step,
        current_equipment_id=lot.current_equipment_id,
        qty=total,
        complete=complete,
        fail=fail,
        scrap=scrap,
        route=steps,
        next_step=nxt["next_step"] if nxt else None,
        next_equipment_id=nxt["next_equipment_id"] if nxt else None,
    )


def mes_board(db: Session) -> MesBoardOut:
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    orders = []
    for order, _panels in list_work_orders(db):
        if order.created_at is None or order.created_at < start:
            continue
        complete, fail, scrap = panel_counts(db, order.lot_id)
        orders.append(
            MesOrderOut(
                id=order.id,
                product_type=order.product_type,
                recipe_id=order.recipe_id,
                qty=order.qty,
                status=order.status,
                lot_id=order.lot_id,
                cassette_id=order.cassette_id,
                complete=complete,
                fail=fail,
                scrap=scrap,
            )
        )

    today_lot_ids = {row.lot_id for row in orders if row.lot_id}
    lots = [
        lot_route_progress(db, lot)
        for lot in db.query(Lot).order_by(Lot.id.asc()).all()
        if lot.id in today_lot_ids or lot.status == LotStatus.HOLD.value
    ]
    equipment = []
    for row in db.query(Equipment).order_by(Equipment.id.asc()).all():
        equipment.append(
            MesEquipmentOut(
                id=row.id,
                process_step=row.process_step,
                product_scope=row.product_scope,
                equipment_status=row.equipment_status,
                connection_status=row.connection_status,
                current_lot_id=row.current_lot_id,
                current_recipe_id=row.current_recipe_id,
            )
        )
    holds = [lot for lot in lots if lot.status == LotStatus.HOLD.value]
    waiting = sum(1 for p in db.query(Panel).all() if p.status == PanelStatus.WAIT.value)
    return MesBoardOut(
        note=NOTE,
        waiting_glass=waiting,
        orders=orders,
        lots=lots,
        equipment=equipment,
        holds=holds,
        production=today_production(db),
        equipment_offline=sum(1 for eq in equipment if eq.connection_status == ConnectionStatus.OFFLINE.value),
    )
