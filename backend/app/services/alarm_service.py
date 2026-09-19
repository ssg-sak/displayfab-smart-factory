from __future__ import annotations

from sqlalchemy.orm import Session

from app.enums import ALARM_SEVERITY_BY_CODE, AlarmCode, AlarmSeverity
from app.models import Alarm
from app.services.timeutil import utcnow


def next_alarm_id(db: Session) -> str:
    last = db.query(Alarm).order_by(Alarm.id.desc()).first()
    if last is None:
        return "ALM-1001"
    try:
        seq = int(last.alarm_id.split("-", 1)[1]) + 1
    except (IndexError, ValueError):
        seq = last.id + 1001
    return f"ALM-{seq}"


def create_alarm(
    db: Session,
    *,
    code: AlarmCode,
    message: str,
    equipment_id: str | None = None,
    lot_id: str | None = None,
    panel_id: str | None = None,
    event_id: str | None = None,
    severity: AlarmSeverity | None = None,
) -> Alarm:
    alarm = Alarm(
        alarm_id=next_alarm_id(db),
        equipment_id=equipment_id,
        lot_id=lot_id,
        panel_id=panel_id,
        event_id=event_id,
        alarm_code=code.value,
        severity=(severity or ALARM_SEVERITY_BY_CODE[code]).value,
        message=message,
        occurred_at=utcnow(),
    )
    db.add(alarm)
    db.flush()
    return alarm


def open_alarm(db: Session, equipment_id: str, code: AlarmCode) -> Alarm | None:
    return (
        db.query(Alarm)
        .filter(
            Alarm.equipment_id == equipment_id,
            Alarm.alarm_code == code.value,
            Alarm.resolved_at.is_(None),
        )
        .first()
    )


def resolve_open_alarms(db: Session, equipment_id: str, code: AlarmCode) -> int:
    rows = (
        db.query(Alarm)
        .filter(
            Alarm.equipment_id == equipment_id,
            Alarm.alarm_code == code.value,
            Alarm.resolved_at.is_(None),
        )
        .all()
    )
    now = utcnow()
    for row in rows:
        row.resolved_at = now
    return len(rows)
