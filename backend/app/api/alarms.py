from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alarm
from app.schemas import AlarmOut

router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.get("", response_model=list[AlarmOut])
def list_alarms(
    db: Session = Depends(get_db),
    equipment_id: str | None = Query(default=None),
    lot_id: str | None = Query(default=None),
    alarm_code: str | None = Query(default=None),
    unresolved_only: bool = Query(default=False),
) -> list[AlarmOut]:
    q = db.query(Alarm)
    if equipment_id:
        q = q.filter(Alarm.equipment_id == equipment_id)
    if lot_id:
        q = q.filter(Alarm.lot_id == lot_id)
    if alarm_code:
        q = q.filter(Alarm.alarm_code == alarm_code)
    if unresolved_only:
        q = q.filter(Alarm.resolved_at.is_(None))
    rows = q.order_by(Alarm.occurred_at.desc(), Alarm.id.desc()).all()
    return rows
