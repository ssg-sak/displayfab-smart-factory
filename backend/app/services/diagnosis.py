from sqlalchemy.orm import Session

from app.domain.rules import route_for
from app.models import Alarm, EventLog, Lot
from app.schemas import AlarmOut, DiagnosisOut


def diagnose_lot(db: Session, lot: Lot) -> DiagnosisOut:
    open_alarms = (
        db.query(Alarm)
        .filter(Alarm.lot_id == lot.id, Alarm.resolved_at.is_(None))
        .order_by(Alarm.occurred_at.desc())
        .all()
    )
    logs = (
        db.query(EventLog)
        .filter(EventLog.lot_id == lot.id)
        .order_by(EventLog.created_at.desc())
        .limit(8)
        .all()
    )
    checks = [
        "open Alarm code vs hold_reason 비교",
        "expected_recipe vs 최근 process_event.recipe_id",
        "OLED/LCD 라우트와 현재 step이 맞는지 확인",
        "event_log에서 reject된 PROCESS가 있는지 확인",
        "설비가 MAINTENANCE/OFFLINE인지 확인",
    ]
    if lot.status != "HOLD":
        checks.insert(0, "HOLD가 아니면 공정 이력과 Cassette 슬롯부터 본다")
    if lot.hold_reason == "INSPECT_FAIL":
        checks.insert(0, "검사 불량: RELEASE 후 재검사하거나 SCRAP_PANEL로 폐기한다")
        summary = f"{lot.id} HOLD. 검사 FAIL. Cassette {lot.cassette_id}."
        action = "RELEASE 후 재검사하거나, 해당 Glass를 SCRAP 한다."
    elif lot.hold_reason == "RECIPE_MISMATCH":
        summary = f"{lot.id} HOLD. Recipe가 LOT 기대값과 다르다."
        action = "왜 다른 Recipe가 보고됐는지 보고, RELEASE 전에 PPID를 맞춘다."
    elif lot.status == "HOLD":
        summary = f"{lot.id} HOLD. reason={lot.hold_reason}."
        action = "Alarm과 event_log를 본 뒤 RELEASE 또는 SCRAP."
    else:
        summary = f"{lot.id} 은 HOLD가 아니다. Cassette {lot.cassette_id}."
        action = "슬롯맵과 공정 이력부터 본다."
    return DiagnosisOut(
        lot_id=lot.id,
        cassette_id=lot.cassette_id,
        product_type=lot.product_type,
        status=lot.status,
        hold_reason=lot.hold_reason,
        route=route_for(lot.product_type),
        current_step=lot.current_step,
        current_equipment_id=lot.current_equipment_id,
        open_alarms=open_alarms,
        last_events=[row.summary for row in logs],
        next_checks=checks,
        summary=summary,
        action=action,
    )
