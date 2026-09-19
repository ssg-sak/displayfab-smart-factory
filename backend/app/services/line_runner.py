from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.domain.rules import IDEAL_CYCLE_SEC
from app.enums import EquipmentStatus, EventType, LotStatus, ProcessStep
from app.models import Lot, Recipe, WorkOrder
from app.schemas import EquipmentEventIn
from app.services.dispatch import lot_dispatch
from app.services.collector import collect_push
from app.services.host_prep import LINE_EQUIPMENT, prepare_equipment, prepare_line, recipe_step, wake_equipment
from app.services.timeutil import utcnow

CYCLE = IDEAL_CYCLE_SEC


def run_work_order(db: Session, work_order_id: str, *, inspect_result: str = "PASS") -> dict:
    order = db.get(WorkOrder, work_order_id)
    if order is None:
        return {"ok": False, "error": f"지시 없음: {work_order_id}"}
    if not order.lot_id:
        return {"ok": False, "error": "지시가 투입되지 않았다"}

    recipe = db.get(Recipe, order.recipe_id)
    temp = 118.4
    pressure = 0.0041
    if recipe:
        temp = round((recipe.expected_temperature_min + recipe.expected_temperature_max) / 2, 2)
        pressure = round((recipe.expected_pressure_min + recipe.expected_pressure_max) / 2, 5)

    prepare_line(db, order.recipe_id)

    results = []
    for i in range(80):
        lot = db.get(Lot, order.lot_id)
        if lot is None:
            return {"ok": False, "error": "LOT 없음", "work_order_id": order.id, "results": results}
        if lot.status == LotStatus.HOLD.value:
            return {
                "ok": False,
                "error": f"LOT HOLD ({lot.hold_reason})",
                "work_order_id": order.id,
                "lot_id": lot.id,
                "results": results,
            }

        info = lot_dispatch(db, lot)
        if info is None or info["done"] or not info.get("next_step"):
            db.refresh(order)
            for eq_id in LINE_EQUIPMENT:
                wake_equipment(db, eq_id)
            return {
                "ok": True,
                "work_order_id": order.id,
                "lot_id": order.lot_id,
                "status": order.status,
                "count": len(results),
                "results": results,
            }

        step = info["next_step"]
        eq_id = info["next_equipment_id"]
        prepare_equipment(db, eq_id, order.recipe_id if recipe_step(step) else None)
        inspect = inspect_result if step == ProcessStep.INSPECT.value else None
        payload = EquipmentEventIn(
            equipment_id=eq_id,
            event_type=EventType.PROCESS,
            lot_id=info["lot_id"],
            panel_id=info["panel_id"],
            process_step=step,
            recipe_id=order.recipe_id,
            equipment_status=EquipmentStatus.RUN,
            chamber_temperature=temp,
            vacuum_pressure=pressure,
            cycle_time_sec=CYCLE.get(step),
            inspect_result=inspect,
            timestamp=utcnow() + timedelta(seconds=i),
        )
        event_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        accepted, reason, alarms, lot_status = collect_push(db, payload, request_id, event_id)
        results.append(
            {
                "accepted": accepted,
                "reason": reason,
                "lot_status": lot_status,
                "panel_id": info["panel_id"],
                "process_step": step,
                "equipment_id": eq_id,
                "alarms": [a.alarm_code for a in alarms],
            }
        )
        if not accepted:
            return {
                "ok": False,
                "error": reason or "rejected",
                "work_order_id": order.id,
                "lot_id": order.lot_id,
                "results": results,
            }

    return {"ok": False, "error": "step limit", "work_order_id": order.id, "results": results}
