from __future__ import annotations

from sqlalchemy.orm import Session

from app.enums import ConnectionStatus, LotStatus, PanelStatus, ProductType
from app.models import Alarm, Equipment, Lot, Panel, WorkOrder
from app.services.timeutil import utcnow


def _day_start():
    return utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def _product_bucket() -> dict:
    return {"target": 0, "complete": 0, "fail": 0, "scrap": 0, "hold_lots": 0}


def _fill_product(db: Session, product: str, orders: list[WorkOrder]) -> dict:
    bucket = _product_bucket()
    for order in orders:
        if order.product_type != product:
            continue
        bucket["target"] += order.qty
        if not order.lot_id:
            continue
        lot = db.get(Lot, order.lot_id)
        if lot and lot.status == LotStatus.HOLD.value:
            bucket["hold_lots"] += 1
        panels = db.query(Panel).filter(Panel.lot_id == order.lot_id).all()
        for panel in panels:
            if panel.status == PanelStatus.COMPLETE.value:
                bucket["complete"] += 1
            elif panel.status == PanelStatus.FAIL.value:
                bucket["fail"] += 1
            elif panel.status == PanelStatus.SCRAP.value:
                bucket["scrap"] += 1
    return bucket


def today_production(db: Session) -> dict:
    start = _day_start()
    orders = db.query(WorkOrder).filter(WorkOrder.created_at >= start).all()
    oled = _fill_product(db, ProductType.OLED.value, orders)
    lcd = _fill_product(db, ProductType.LCD.value, orders)

    hold_lots = [
        lot.id for lot in db.query(Lot).filter(Lot.status == LotStatus.HOLD.value).order_by(Lot.id.asc()).all()
    ]
    offline = [
        eq.id
        for eq in db.query(Equipment)
        .filter(Equipment.connection_status == ConnectionStatus.OFFLINE.value)
        .order_by(Equipment.id.asc())
        .all()
    ]
    open_alarms = db.query(Alarm).filter(Alarm.resolved_at.is_(None)).count()
    parts = [
        f"올레드 완료 {oled['complete']} / 목표 {oled['target']}",
        f"엘시디 완료 {lcd['complete']} / 목표 {lcd['target']}",
    ]
    blocked = []
    if hold_lots:
        blocked.append("보류 " + ",".join(hold_lots))
    if offline:
        blocked.append("끊김 " + ",".join(offline))
    target = oled["target"] + lcd["target"]
    complete = oled["complete"] + lcd["complete"]
    fail = oled["fail"] + lcd["fail"]
    scrap = oled["scrap"] + lcd["scrap"]
    judged = complete + fail + scrap
    remaining = max(target - judged, 0)
    yield_pct = round(100.0 * complete / judged, 1) if judged else None
    date = start.strftime("%Y-%m-%d")
    return {
        "date": date,
        "oled": oled,
        "lcd": lcd,
        "hold_lots": hold_lots,
        "offline_equipment": offline,
        "open_alarms": open_alarms,
        "summary": "  ·  ".join(parts),
        "blocked": "  ·  ".join(blocked) if blocked else "막힌 것 없음",
        "closeout": {
            "target": target,
            "complete": complete,
            "fail": fail,
            "scrap": scrap,
            "remaining": remaining,
            "hold_lots": len(hold_lots),
            "offline": len(offline),
            "yield_pct": yield_pct,
            "line": (
                f"오늘 {date}  완료 {complete}/{target}  불량 {fail}  "
                f"보류 {len(hold_lots)}  끊김 {len(offline)}"
            ),
        },
    }
