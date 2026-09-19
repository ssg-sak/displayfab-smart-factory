from app.models import EventLog
from app.schemas import EquipmentEventIn
from app.services.timeutil import utcnow
from sqlalchemy.orm import Session


def write_event_log(
    db: Session,
    *,
    event_id: str,
    request_id: str,
    payload: EquipmentEventIn,
    accepted: bool,
    reason: str | None,
) -> EventLog:
    event_type = payload.event_type.value if hasattr(payload.event_type, "value") else str(payload.event_type)
    row = EventLog(
        event_id=event_id,
        request_id=request_id,
        event_type=event_type,
        accepted=accepted,
        reason=reason,
        equipment_id=payload.equipment_id,
        lot_id=payload.lot_id,
        panel_id=payload.panel_id,
        process_step=payload.process_step,
        summary=(
            f"{event_type} {payload.equipment_id} lot={payload.lot_id or '-'} "
            f"glass={payload.panel_id or '-'} step={payload.process_step or '-'} "
            f"accepted={accepted} reason={reason or '-'}"
        ),
        created_at=utcnow(),
    )
    db.add(row)
    return row
