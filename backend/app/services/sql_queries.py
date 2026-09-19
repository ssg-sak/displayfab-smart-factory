from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.enums import AlarmCode, ConnectionStatus, LotStatus
from app.models import Alarm, Equipment, Lot, ProcessEvent, SensorReading
from app.services.timeutil import utcnow


def equipment_with_most_alarms_today(db: Session) -> list[tuple[str, int]]:
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.query(Alarm.equipment_id, func.count(Alarm.id))
        .filter(Alarm.occurred_at >= start, Alarm.equipment_id.is_not(None))
        .group_by(Alarm.equipment_id)
        .order_by(func.count(Alarm.id).desc())
        .all()
    )
    return [(eid, count) for eid, count in rows]


def lots_with_recipe_mismatch(db: Session) -> list[str]:
    rows = (
        db.query(Alarm.lot_id)
        .filter(Alarm.alarm_code == AlarmCode.RECIPE_MISMATCH.value, Alarm.lot_id.is_not(None))
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def hold_lots(db: Session) -> list[Lot]:
    return db.query(Lot).filter(Lot.status == LotStatus.HOLD.value).all()


def avg_cycle_time_by_equipment(db: Session) -> list[tuple[str, float]]:
    rows = (
        db.query(ProcessEvent.equipment_id, func.avg(ProcessEvent.cycle_time_sec))
        .filter(ProcessEvent.cycle_time_sec.is_not(None))
        .group_by(ProcessEvent.equipment_id)
        .order_by(func.avg(ProcessEvent.cycle_time_sec).desc())
        .all()
    )
    return [(eid, float(avg)) for eid, avg in rows]


def panel_count_by_equipment(db: Session) -> list[tuple[str, int]]:
    rows = (
        db.query(ProcessEvent.equipment_id, func.count(func.distinct(ProcessEvent.panel_id)))
        .group_by(ProcessEvent.equipment_id)
        .all()
    )
    return [(eid, int(count)) for eid, count in rows]


def avg_cycle_time_by_recipe(db: Session) -> list[tuple[str, float]]:
    rows = (
        db.query(ProcessEvent.recipe_id, func.avg(ProcessEvent.cycle_time_sec))
        .filter(ProcessEvent.recipe_id.is_not(None), ProcessEvent.cycle_time_sec.is_not(None))
        .group_by(ProcessEvent.recipe_id)
        .all()
    )
    return [(rid, float(avg)) for rid, avg in rows]


def offline_equipment_last_hour(db: Session) -> list[str]:
    since = utcnow() - timedelta(hours=1)
    alarm_ids = (
        db.query(Alarm.equipment_id)
        .filter(
            Alarm.alarm_code == AlarmCode.COMMUNICATION_LOSS.value,
            Alarm.occurred_at >= since,
            Alarm.equipment_id.is_not(None),
        )
        .distinct()
    )
    still_offline = db.query(Equipment.id).filter(
        Equipment.connection_status == ConnectionStatus.OFFLINE.value
    )
    ids = {row[0] for row in alarm_ids} | {row[0] for row in still_offline}
    return sorted(ids)


def recent_events_for_equipment(db: Session, equipment_id: str, limit: int = 20) -> list[ProcessEvent]:
    return (
        db.query(ProcessEvent)
        .filter(ProcessEvent.equipment_id == equipment_id)
        .order_by(ProcessEvent.event_timestamp.desc())
        .limit(limit)
        .all()
    )


def unused_sensor_join_example(db: Session):
    """ORM에서 process_event와 sensor_reading을 나누는 이유를 보여주기 위한 참조용."""
    return (
        db.query(ProcessEvent, SensorReading)
        .join(SensorReading, SensorReading.process_event_id == ProcessEvent.id)
        .limit(1)
        .all()
    )
