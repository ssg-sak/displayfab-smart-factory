import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.enums import AlarmCode, ConnectionStatus, DowntimeReason
from app.logging_setup import bind_event_id, bind_request_id, get_logger
from app.models import Equipment
from app.services.alarm_service import create_alarm, open_alarm
from app.services.downtime import open_downtime
from app.services.timeutil import utcnow

logger = get_logger(__name__)


def mark_offline_equipment(db: Session) -> list[str]:
    """데이터가 일정 시간 없으면 Connection만 OFFLINE으로 바꾼다. Equipment status는 마지막 보고를 유지한다."""
    bind_request_id("offline-detector")
    bind_event_id("-")
    now = utcnow()
    changed: list[str] = []
    rows = db.query(Equipment).all()
    for eq in rows:
        if eq.last_seen_at is None:
            if eq.connection_status != ConnectionStatus.OFFLINE.value:
                eq.connection_status = ConnectionStatus.OFFLINE.value
                changed.append(eq.id)
            continue
        silent_for = (now - eq.last_seen_at).total_seconds()
        if silent_for >= settings.communication_timeout_sec:
            if eq.connection_status != ConnectionStatus.OFFLINE.value:
                eq.connection_status = ConnectionStatus.OFFLINE.value
                if open_alarm(db, eq.id, AlarmCode.COMMUNICATION_LOSS) is None:
                    create_alarm(
                        db,
                        code=AlarmCode.COMMUNICATION_LOSS,
                        message=f"{eq.id}에서 {int(silent_for)}초 동안 신호가 없습니다",
                        equipment_id=eq.id,
                    )
                    logger.error("COMMUNICATION_LOSS equipment=%s silent_for=%ss", eq.id, int(silent_for))
                open_downtime(db, eq.id, DowntimeReason.COMMUNICATION_LOSS.value)
                changed.append(eq.id)
    if changed:
        db.commit()
    return changed
