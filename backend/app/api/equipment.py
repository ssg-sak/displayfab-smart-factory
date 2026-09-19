from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.adapters.registry import get_adapter
from app.database import get_db
from app.models import Alarm, Equipment, EquipmentDowntime, Telemetry
from app.schemas import (
    DowntimeOut,
    EquipmentInterfaceBriefOut,
    EquipmentInterfaceOut,
    EquipmentOut,
    TelemetryOut,
)
from app.services.oee import downtime_seconds

router = APIRouter(prefix="/equipment", tags=["equipment"])


def _to_out(db: Session, row: Equipment) -> EquipmentOut:
    open_count = (
        db.query(Alarm)
        .filter(Alarm.equipment_id == row.id, Alarm.resolved_at.is_(None))
        .count()
    )
    return EquipmentOut(
        id=row.id,
        name=row.name,
        process_step=row.process_step,
        product_scope=row.product_scope,
        equipment_status=row.equipment_status,
        connection_status=row.connection_status,
        current_lot_id=row.current_lot_id,
        current_recipe_id=row.current_recipe_id,
        last_seen_at=row.last_seen_at,
        interface_type=row.interface_type or "simulator",
        interface_endpoint=row.interface_endpoint,
        open_alarm_count=open_count,
    )


def _last_telemetry(db: Session, equipment_id: str) -> Telemetry | None:
    return (
        db.query(Telemetry)
        .filter(Telemetry.equipment_id == equipment_id)
        .order_by(Telemetry.recorded_at.desc(), Telemetry.id.desc())
        .first()
    )


@router.get("", response_model=list[EquipmentOut])
def list_equipment(db: Session = Depends(get_db)) -> list[EquipmentOut]:
    rows = db.query(Equipment).order_by(Equipment.id.asc()).all()
    return [_to_out(db, row) for row in rows]


@router.get("/interfaces", response_model=list[EquipmentInterfaceBriefOut])
def list_equipment_interfaces(db: Session = Depends(get_db)) -> list[EquipmentInterfaceBriefOut]:
    """운전 화면용. 설비별 통신 방식 · 마지막 측정값 · 오늘 정지시간을 한 번에 준다."""
    rows = db.query(Equipment).order_by(Equipment.id.asc()).all()
    downtime = downtime_seconds(db)
    open_reason = {
        row.equipment_id: row.reason
        for row in db.query(EquipmentDowntime)
        .filter(EquipmentDowntime.ended_at.is_(None))
        .order_by(EquipmentDowntime.started_at.asc())
        .all()
    }
    out: list[EquipmentInterfaceBriefOut] = []
    for row in rows:
        adapter = get_adapter(row.interface_type, db)
        last = _last_telemetry(db, row.id)
        count = db.query(Telemetry).filter(Telemetry.equipment_id == row.id).count()
        out.append(
            EquipmentInterfaceBriefOut(
                equipment_id=row.id,
                interface_type=row.interface_type or "simulator",
                transport=getattr(adapter, "transport", None),
                connection_status=row.connection_status,
                last_seen_at=row.last_seen_at,
                chamber_temperature=last.chamber_temperature if last else None,
                vacuum_pressure=last.vacuum_pressure if last else None,
                recorded_at=last.recorded_at if last else None,
                telemetry_count=count,
                downtime_sec_today=round(downtime.get(row.id, 0.0), 1),
                open_downtime_reason=open_reason.get(row.id),
            )
        )
    return out


@router.get("/{equipment_id}/interface", response_model=EquipmentInterfaceOut)
def get_equipment_interface(equipment_id: str, db: Session = Depends(get_db)) -> EquipmentInterfaceOut:
    row = db.get(Equipment, equipment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    adapter = get_adapter(row.interface_type, db)
    poll_implemented = adapter.name == "simulator"
    last = _last_telemetry(db, row.id)
    open_rows = (
        db.query(EquipmentDowntime)
        .filter(EquipmentDowntime.equipment_id == row.id, EquipmentDowntime.ended_at.is_(None))
        .order_by(EquipmentDowntime.started_at.desc())
        .all()
    )
    return EquipmentInterfaceOut(
        equipment_id=row.id,
        interface_type=row.interface_type or "simulator",
        interface_endpoint=row.interface_endpoint,
        adapter=adapter.name,
        transport=getattr(adapter, "transport", None),
        poll_implemented=poll_implemented,
        connection_status=row.connection_status,
        equipment_status=row.equipment_status,
        last_seen_at=row.last_seen_at,
        last_telemetry=TelemetryOut.model_validate(last) if last else None,
        open_downtime=[DowntimeOut.model_validate(d) for d in open_rows],
    )


@router.get("/{equipment_id}/telemetry", response_model=list[TelemetryOut])
def list_equipment_telemetry(
    equipment_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=200),
) -> list[TelemetryOut]:
    row = db.get(Equipment, equipment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    rows = (
        db.query(Telemetry)
        .filter(Telemetry.equipment_id == equipment_id)
        .order_by(Telemetry.recorded_at.desc(), Telemetry.id.desc())
        .limit(limit)
        .all()
    )
    return [TelemetryOut.model_validate(item) for item in rows]


@router.get("/{equipment_id}/downtime", response_model=list[DowntimeOut])
def list_equipment_downtime(
    equipment_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=200),
) -> list[DowntimeOut]:
    row = db.get(Equipment, equipment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    rows = (
        db.query(EquipmentDowntime)
        .filter(EquipmentDowntime.equipment_id == equipment_id)
        .order_by(EquipmentDowntime.started_at.desc())
        .limit(limit)
        .all()
    )
    return [DowntimeOut.model_validate(item) for item in rows]


@router.get("/{equipment_id}", response_model=EquipmentOut)
def get_equipment(equipment_id: str, db: Session = Depends(get_db)) -> EquipmentOut:
    row = db.get(Equipment, equipment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return _to_out(db, row)
