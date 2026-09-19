from datetime import timedelta

from sqlalchemy.orm import Session

from app.enums import ConnectionStatus, LotStatus, PanelStatus, ProcessStep, ProductType
from app.models import Alarm, Equipment, EventLog, Lot, Panel, ProcessEvent
from app.schemas import KpiOut, YieldByEquipmentOut
from app.services.timeutil import utcnow


def yield_by_equipment(db: Session) -> list[YieldByEquipmentOut]:
    judged = db.query(Panel).filter(Panel.status.in_([PanelStatus.COMPLETE.value, PanelStatus.FAIL.value])).all()
    buckets: dict[str, list[int]] = {}
    for panel in judged:
        last = (
            db.query(ProcessEvent)
            .filter(
                ProcessEvent.panel_id == panel.id,
                ProcessEvent.process_step != ProcessStep.INSPECT.value,
            )
            .order_by(ProcessEvent.event_timestamp.desc(), ProcessEvent.id.desc())
            .first()
        )
        eq_id = last.equipment_id if last else "-"
        pair = buckets.setdefault(eq_id, [0, 0])
        if panel.status == PanelStatus.COMPLETE.value:
            pair[0] += 1
        else:
            pair[1] += 1
    rows = []
    for eq_id, (complete, fail) in sorted(buckets.items()):
        total = complete + fail
        rows.append(
            YieldByEquipmentOut(
                equipment_id=eq_id,
                complete=complete,
                fail=fail,
                yield_pct=round(100.0 * complete / total, 1) if total else None,
            )
        )
    return rows


def kpis(db: Session) -> KpiOut:
    total = db.query(Equipment).count()
    online = db.query(Equipment).filter(Equipment.connection_status == ConnectionStatus.ONLINE.value).count()
    inspect_pass = db.query(Panel).filter(Panel.status == PanelStatus.COMPLETE.value).count()
    inspect_fail = db.query(Panel).filter(Panel.status == PanelStatus.FAIL.value).count()
    inspect_scrap = db.query(Panel).filter(Panel.status == PanelStatus.SCRAP.value).count()
    judged = inspect_pass + inspect_fail + inspect_scrap
    yield_pct = round(100.0 * inspect_pass / judged, 1) if judged else None
    since = utcnow() - timedelta(minutes=5)
    return KpiOut(
        equipment_online=online,
        equipment_offline=total - online,
        lots_hold=db.query(Lot).filter(Lot.status == LotStatus.HOLD.value).count(),
        lots_processing=db.query(Lot).filter(Lot.status == LotStatus.PROCESSING.value).count(),
        open_alarms=db.query(Alarm).filter(Alarm.resolved_at.is_(None)).count(),
        events_last_5min=db.query(EventLog).filter(EventLog.created_at >= since).count(),
        oled_lots=db.query(Lot).filter(Lot.product_type == ProductType.OLED.value).count(),
        lcd_lots=db.query(Lot).filter(Lot.product_type == ProductType.LCD.value).count(),
        inspect_pass=inspect_pass,
        inspect_fail=inspect_fail,
        inspect_scrap=inspect_scrap,
        yield_pct=yield_pct,
        yield_by_equipment=yield_by_equipment(db),
    )
