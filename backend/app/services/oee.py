"""OEE = Availability × Performance × Quality.

가짜 가동시간을 만들지 않는다. 세 재료는 모두 이미 쌓인 데이터에서 온다.

  Availability  계획가동시간 - equipment_downtime
  Performance   이론 사이클(domain/rules.IDEAL_CYCLE_SEC) × 처리수 / 가동시간
  Quality       COMPLETE / (COMPLETE + FAIL + SCRAP)

계획가동시간은 이 시스템이 정한 기준이다.
  settings.oee_planned_minutes > 0  →  지금부터 거꾸로 그 시간
  0 (기본)                          →  오늘 설비가 처음 보고한 시각부터 지금까지
오늘 아무 보고가 없으면 라인이 열리지 않은 것으로 보고 OEE를 내지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.rules import ideal_cycle_sec
from app.enums import PanelStatus
from app.models import Equipment, EquipmentDowntime, Panel, ProcessEvent, Telemetry
from app.services.timeutil import utcnow


def _day_start() -> datetime:
    return utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def line_open_at(db: Session) -> datetime | None:
    """오늘 설비가 처음 보고한 시각. 이게 없으면 라인이 열리지 않았다."""
    day = _day_start()
    first_telemetry = (
        db.query(Telemetry.recorded_at)
        .filter(Telemetry.recorded_at >= day)
        .order_by(Telemetry.recorded_at.asc())
        .limit(1)
        .scalar()
    )
    first_event = (
        db.query(ProcessEvent.event_timestamp)
        .filter(ProcessEvent.event_timestamp >= day)
        .order_by(ProcessEvent.event_timestamp.asc())
        .limit(1)
        .scalar()
    )
    stamps = [value for value in (first_telemetry, first_event) if value is not None]
    return min(stamps) if stamps else None


def planned_window(db: Session) -> tuple[datetime | None, datetime, float]:
    """(계획시간 시작, 지금, 계획시간 초). 시작이 None이면 계획시간이 없다."""
    now = utcnow()
    if settings.oee_planned_minutes > 0:
        start = now - timedelta(minutes=settings.oee_planned_minutes)
        return start, now, float(settings.oee_planned_minutes * 60)
    opened = line_open_at(db)
    if opened is None:
        return None, now, 0.0
    start = max(opened, _day_start())
    return start, now, max((now - start).total_seconds(), 1.0)


def downtime_seconds(db: Session, equipment_id: str | None = None) -> dict[str, float]:
    """설비별 정지시간. 계획시간 안에 들어오는 구간만, 열린 구간은 지금까지로 센다."""
    start, now, planned = planned_window(db)
    if start is None:
        return {}
    q = db.query(EquipmentDowntime).filter(
        (EquipmentDowntime.ended_at.is_(None)) | (EquipmentDowntime.ended_at >= start)
    )
    if equipment_id:
        q = q.filter(EquipmentDowntime.equipment_id == equipment_id)
    totals: dict[str, float] = {}
    for row in q.all():
        began = max(row.started_at, start)
        ended = row.ended_at or now
        seconds = (ended - began).total_seconds()
        if seconds <= 0:
            continue
        totals[row.equipment_id] = totals.get(row.equipment_id, 0.0) + seconds
    return totals


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(min(numerator / denominator, 1.0), 4)


def _panel_quality(db: Session, panel_ids: set[str]) -> tuple[int, int]:
    if not panel_ids:
        return 0, 0
    rows = db.query(Panel.status).filter(Panel.id.in_(panel_ids)).all()
    good = sum(1 for (status,) in rows if status == PanelStatus.COMPLETE.value)
    bad = sum(
        1
        for (status,) in rows
        if status in (PanelStatus.FAIL.value, PanelStatus.SCRAP.value)
    )
    return good, bad


def equipment_oee(db: Session, equipment_id: str) -> dict:
    start, _now, planned = planned_window(db)
    events = (
        db.query(ProcessEvent)
        .filter(
            ProcessEvent.equipment_id == equipment_id,
            ProcessEvent.event_timestamp >= (start or _day_start()),
        )
        .all()
    )
    downtime = downtime_seconds(db, equipment_id).get(equipment_id, 0.0)
    operating = max(planned - downtime, 0.0)

    ideal_total = 0.0
    for event in events:
        ideal = ideal_cycle_sec(event.process_step)
        if ideal:
            ideal_total += ideal

    good, bad = _panel_quality(db, {event.panel_id for event in events})

    availability = _ratio(operating, planned)
    performance = _ratio(ideal_total, operating) if ideal_total else None
    quality = _ratio(good, good + bad) if (good + bad) else None
    oee = None
    if availability is not None and performance is not None and quality is not None:
        oee = round(availability * performance * quality, 4)

    return {
        "equipment_id": equipment_id,
        "processed": len(events),
        "good": good,
        "bad": bad,
        "planned_sec": round(planned, 1),
        "downtime_sec": round(downtime, 1),
        "operating_sec": round(operating, 1),
        "ideal_runtime_sec": round(ideal_total, 1),
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": oee,
    }


def line_oee(db: Session) -> dict:
    rows = [
        equipment_oee(db, eq.id)
        for eq in db.query(Equipment).order_by(Equipment.id.asc()).all()
    ]
    start, _now, planned = planned_window(db)
    total_planned = planned * len(rows) if rows else 0.0
    total_downtime = sum(row["downtime_sec"] for row in rows)
    total_operating = max(total_planned - total_downtime, 0.0)
    total_ideal = sum(row["ideal_runtime_sec"] for row in rows)

    # 유리 한 장은 여러 설비를 지난다. 라인 품질은 설비별 합이 아니라 유리 단위로 센다.
    today_panels = {
        panel_id
        for (panel_id,) in db.query(ProcessEvent.panel_id)
        .filter(ProcessEvent.event_timestamp >= (start or _day_start()))
        .distinct()
        .all()
    }
    good, bad = _panel_quality(db, today_panels)

    availability = _ratio(total_operating, total_planned)
    performance = _ratio(total_ideal, total_operating) if total_ideal else None
    quality = _ratio(good, good + bad) if (good + bad) else None
    oee = None
    if availability is not None and performance is not None and quality is not None:
        oee = round(availability * performance * quality, 4)

    missing = []
    if start is None:
        missing.append("오늘 설비 보고가 없어 계획가동시간이 없다")
    if performance is None:
        missing.append("오늘 실적이 없어 Performance를 못 낸다")
    if quality is None:
        missing.append("판정된 유리가 없어 Quality를 못 낸다")

    if settings.oee_planned_minutes > 0:
        basis = f"설정 {settings.oee_planned_minutes}분"
    elif start is None:
        basis = "라인이 오늘 열리지 않았다"
    else:
        basis = f"오늘 첫 보고 {start.strftime('%H:%M:%S')} 부터 지금까지"

    return {
        "date": _day_start().strftime("%Y-%m-%d"),
        "planned_basis": basis,
        "planned_sec": round(planned, 1),
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": oee,
        "good": good,
        "bad": bad,
        "note": (
            "계획가동시간과 이론 사이클은 이 시스템이 정한 기준이다. 현장 스펙이 아니다."
        ),
        "missing": missing,
        "equipment": rows,
    }
