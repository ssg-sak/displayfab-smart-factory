from sqlalchemy.orm import Session

from app.models import EquipmentDowntime
from app.services.timeutil import utcnow


def open_downtime(
    db: Session,
    equipment_id: str,
    reason: str,
    event_id: str | None = None,
) -> EquipmentDowntime:
    existing = (
        db.query(EquipmentDowntime)
        .filter(
            EquipmentDowntime.equipment_id == equipment_id,
            EquipmentDowntime.reason == reason,
            EquipmentDowntime.ended_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        return existing
    row = EquipmentDowntime(
        equipment_id=equipment_id,
        reason=reason,
        started_at=utcnow(),
        event_id=event_id,
    )
    db.add(row)
    return row


def close_downtime(
    db: Session,
    equipment_id: str,
    reasons: list[str] | None = None,
) -> int:
    q = db.query(EquipmentDowntime).filter(
        EquipmentDowntime.equipment_id == equipment_id,
        EquipmentDowntime.ended_at.is_(None),
    )
    if reasons:
        q = q.filter(EquipmentDowntime.reason.in_(reasons))
    now = utcnow()
    closed = 0
    for row in q.all():
        row.ended_at = now
        row.duration_sec = (now - row.started_at).total_seconds()
        closed += 1
    return closed
