from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.rules import LCD_ROUTE, OLED_ROUTE, equipment_ids_for_step, next_operation, normalize_step
from app.enums import ConnectionStatus, EquipmentStatus, PanelStatus, ProcessStep
from app.models import Equipment, Lot, Panel, ProcessEvent


def last_step(db: Session, panel_id: str) -> str | None:
    row = (
        db.query(ProcessEvent)
        .filter(ProcessEvent.panel_id == panel_id)
        .order_by(ProcessEvent.event_timestamp.desc(), ProcessEvent.id.desc())
        .first()
    )
    return normalize_step(row.process_step) if row else None


def pick_equipment(db: Session, step: str | None) -> str | None:
    ids = equipment_ids_for_step(step)
    if not ids:
        return None
    rows = [db.get(Equipment, equipment_id) for equipment_id in ids]
    rows = [row for row in rows if row is not None]

    def score(eq: Equipment) -> int:
        if eq.equipment_status == EquipmentStatus.MAINTENANCE.value:
            return 50
        if eq.equipment_status == EquipmentStatus.STOP.value:
            return 40
        if eq.connection_status == ConnectionStatus.OFFLINE.value:
            return 30
        if eq.current_lot_id:
            return 20
        if eq.equipment_status == EquipmentStatus.RUN.value:
            return 10
        return 0

    rows.sort(key=score)
    return rows[0].id if rows else ids[0]


def panel_dispatch(db: Session, panel: Panel) -> dict:
    lot = panel.lot or db.get(Lot, panel.lot_id)
    last = last_step(db, panel.id)
    nxt_step, nxt_eq = next_operation(lot.product_type, last)
    if nxt_step:
        nxt_eq = pick_equipment(db, nxt_step) or nxt_eq
    if panel.status == PanelStatus.SCRAP.value:
        nxt_step, nxt_eq = None, None
        done = True
    elif panel.status == PanelStatus.COMPLETE.value:
        nxt_step, nxt_eq = None, None
        done = True
    elif panel.status == PanelStatus.FAIL.value:
        nxt_step, nxt_eq = ProcessStep.INSPECT.value, "INSPECT-01"
        done = False
    else:
        done = nxt_step is None
    at_eq = lot.current_equipment_id if last else nxt_eq
    return {
        "panel_id": panel.id,
        "lot_id": lot.id,
        "cassette_id": lot.cassette_id,
        "product_type": lot.product_type,
        "recipe_id": lot.expected_recipe_id,
        "lot_status": lot.status,
        "panel_status": panel.status,
        "last_step": last,
        "next_step": None if done else nxt_step,
        "next_equipment_id": None if done else nxt_eq,
        "at_equipment_id": at_eq,
        "done": done,
    }


def lot_dispatch(db: Session, lot: Lot) -> dict | None:
    panels = db.query(Panel).filter(Panel.lot_id == lot.id).order_by(Panel.slot_no.asc()).all()
    for panel in panels:
        if panel.status in (PanelStatus.FAIL.value, PanelStatus.SCRAP.value):
            continue
        info = panel_dispatch(db, panel)
        if not info["done"]:
            return info
    if not panels:
        return None
    return panel_dispatch(db, panels[-1])


def line_wip(db: Session) -> dict:
    steps = list(dict.fromkeys(OLED_ROUTE + LCD_ROUTE))
    by_step = {step: 0 for step in steps}
    complete = 0
    fail = 0
    scrap = 0
    cassettes = []

    lots = db.query(Lot).order_by(Lot.id.asc()).all()
    for lot in lots:
        panels = db.query(Panel).filter(Panel.lot_id == lot.id).order_by(Panel.slot_no.asc()).all()
        lot_next = None
        lot_eq = lot.current_equipment_id
        for panel in panels:
            if panel.status == PanelStatus.SCRAP.value:
                scrap += 1
                continue
            if panel.status == PanelStatus.FAIL.value:
                fail += 1
                continue
            info = panel_dispatch(db, panel)
            if info["done"]:
                complete += 1
                continue
            by_step[info["next_step"]] = by_step.get(info["next_step"], 0) + 1
            if lot_next is None:
                lot_next = info["next_step"]
                lot_eq = info["next_equipment_id"] or info["at_equipment_id"]
        cassettes.append(
            {
                "lot_id": lot.id,
                "cassette_id": lot.cassette_id,
                "product_type": lot.product_type,
                "status": lot.status,
                "at_equipment_id": lot_eq,
                "next_step": lot_next,
            }
        )

    return {
        "by_step": by_step,
        "complete": complete,
        "fail": fail,
        "scrap": scrap,
        "cassettes": cassettes,
    }
