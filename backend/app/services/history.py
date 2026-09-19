from sqlalchemy.orm import Session, joinedload

from app.models import Lot, Panel, ProcessEvent
from app.schemas import ProcessHistoryItem, TravelerOut, TravelerSlotOut


def events_to_history(rows: list[ProcessEvent]) -> list[ProcessHistoryItem]:
    items: list[ProcessHistoryItem] = []
    for row in rows:
        reading = row.sensor_reading
        items.append(
            ProcessHistoryItem(
                event_id=row.event_id,
                event_type=row.event_type,
                equipment_id=row.equipment_id,
                lot_id=row.lot_id,
                panel_id=row.panel_id,
                process_step=row.process_step,
                recipe_id=row.recipe_id,
                equipment_status=row.equipment_status,
                cycle_time_sec=row.cycle_time_sec,
                chamber_temperature=reading.chamber_temperature if reading else None,
                vacuum_pressure=reading.vacuum_pressure if reading else None,
                inspect_result=row.inspect_result,
                event_timestamp=row.event_timestamp,
                received_at=row.received_at,
            )
        )
    return items


def lot_history(db: Session, lot_id: str) -> list[ProcessHistoryItem]:
    rows = (
        db.query(ProcessEvent)
        .options(joinedload(ProcessEvent.sensor_reading))
        .filter(ProcessEvent.lot_id == lot_id)
        .order_by(ProcessEvent.event_timestamp.asc(), ProcessEvent.id.asc())
        .all()
    )
    return events_to_history(rows)


def lot_traveler(db: Session, lot: Lot) -> TravelerOut:
    panels = db.query(Panel).filter(Panel.lot_id == lot.id).order_by(Panel.slot_no.asc()).all()
    slots = []
    for panel in panels:
        last = (
            db.query(ProcessEvent)
            .filter(ProcessEvent.panel_id == panel.id)
            .order_by(ProcessEvent.event_timestamp.desc(), ProcessEvent.id.desc())
            .first()
        )
        slots.append(
            TravelerSlotOut(
                slot_no=panel.slot_no,
                panel_id=panel.id,
                status=panel.status,
                last_step=last.process_step if last else None,
                last_equipment_id=last.equipment_id if last else None,
                last_at=last.event_timestamp if last else None,
            )
        )
    return TravelerOut(
        lot_id=lot.id,
        cassette_id=lot.cassette_id,
        product_type=lot.product_type,
        recipe_id=lot.expected_recipe_id,
        status=lot.status,
        hold_reason=lot.hold_reason,
        current_step=lot.current_step,
        current_equipment_id=lot.current_equipment_id,
        slots=slots,
    )


def panel_history(db: Session, panel_id: str) -> list[ProcessHistoryItem]:
    rows = (
        db.query(ProcessEvent)
        .options(joinedload(ProcessEvent.sensor_reading))
        .filter(ProcessEvent.panel_id == panel_id)
        .order_by(ProcessEvent.event_timestamp.asc(), ProcessEvent.id.asc())
        .all()
    )
    return events_to_history(rows)
