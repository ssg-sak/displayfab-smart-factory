from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.rules import normalize_step
from app.enums import (
    AlarmCode,
    ConnectionStatus,
    DowntimeReason,
    EquipmentStatus,
    EventType,
    InspectResult,
    LotStatus,
    PanelStatus,
    ProcessStep,
)
from app.logging_setup import bind_event_id, get_logger
from app.models import Equipment, Lot, Panel, ProcessEvent, Recipe, SensorReading
from app.schemas import EquipmentEventIn
from app.services.alarm_service import create_alarm, resolve_open_alarms
from app.services.downtime import close_downtime
from app.services.event_bus import publish
from app.services.event_log import write_event_log
from app.services.fingerprint import event_fingerprint
from app.services.state_change import record_state_change
from app.services.timeutil import as_naive_utc, utcnow
from app.services.work_orders import refresh_work_order_for_lot
from app.services.validation import validate_event

logger = get_logger(__name__)


def _lot_all_panels_complete(db: Session, lot_id: str) -> bool:
    remaining = (
        db.query(Panel)
        .filter(
            Panel.lot_id == lot_id,
            Panel.status.notin_([PanelStatus.COMPLETE.value, PanelStatus.SCRAP.value]),
        )
        .count()
    )
    return remaining == 0


def ingest_event(
    db: Session,
    payload: EquipmentEventIn,
    request_id: str,
    event_id: str,
) -> tuple[bool, str | None, list, str | None]:
    bind_event_id(event_id)
    event_type = payload.event_type.value if hasattr(payload.event_type, "value") else str(payload.event_type)
    step = normalize_step(payload.process_step)
    logger.info(
        "EVENT_RECEIVED type=%s equipment=%s lot=%s glass=%s step=%s recipe=%s product_hint=%s",
        event_type,
        payload.equipment_id,
        payload.lot_id,
        payload.panel_id,
        step,
        payload.recipe_id,
        request_id,
    )

    if payload.force_db_failure:
        logger.error("DATABASE_WRITE_FAILED forced by client flag")
        known = db.get(Equipment, payload.equipment_id)
        alarm = create_alarm(
            db,
            code=AlarmCode.DB_WRITE_FAILURE,
            message="Forced DB write failure for lab testing",
            equipment_id=known.id if known else None,
            lot_id=payload.lot_id,
            panel_id=payload.panel_id,
            event_id=event_id,
        )
        write_event_log(db, event_id=event_id, request_id=request_id, payload=payload, accepted=False, reason=AlarmCode.DB_WRITE_FAILURE.value)
        db.commit()
        publish({"type": "event", "accepted": False, "reason": AlarmCode.DB_WRITE_FAILURE.value, "event_id": event_id})
        return False, AlarmCode.DB_WRITE_FAILURE.value, [alarm], None

    checks = validate_event(db, payload)
    reject = next((c for c in checks if c.reject), None)
    alarms = []

    equipment = db.get(Equipment, payload.equipment_id)
    if equipment is not None:
        equipment.last_seen_at = utcnow()
        equipment.connection_status = ConnectionStatus.ONLINE.value
        resolve_open_alarms(db, equipment.id, AlarmCode.COMMUNICATION_LOSS)
        close_downtime(db, equipment.id, reasons=[DowntimeReason.COMMUNICATION_LOSS.value])

    if event_type == EventType.HEARTBEAT.value and reject is None:
        if equipment is not None and payload.equipment_status:
            prev = equipment.equipment_status
            if payload.equipment_status.value == EquipmentStatus.IDLE.value:
                equipment.equipment_status = EquipmentStatus.IDLE.value
            record_state_change(
                db,
                entity_type="EQUIPMENT",
                entity_id=equipment.id,
                from_status=prev,
                to_status=equipment.equipment_status,
                reason="heartbeat",
                event_id=event_id,
            )
        write_event_log(db, event_id=event_id, request_id=request_id, payload=payload, accepted=True, reason=None)
        db.commit()
        publish({"type": "heartbeat", "equipment_id": payload.equipment_id, "event_id": event_id})
        logger.info("HEARTBEAT equipment=%s", payload.equipment_id)
        return True, None, [], None

    if reject is not None:
        logger.error("%s %s", reject.code.value if reject.code else "REJECT", reject.message)
        alarm = create_alarm(
            db,
            code=reject.code or AlarmCode.INVALID_LOT,
            message=reject.message,
            equipment_id=equipment.id if equipment is not None else None,
            lot_id=payload.lot_id,
            panel_id=payload.panel_id,
            event_id=event_id,
            severity=reject.severity,
        )
        alarms.append(alarm)
        write_event_log(
            db,
            event_id=event_id,
            request_id=request_id,
            payload=payload,
            accepted=False,
            reason=reject.code.value if reject.code else "REJECTED",
        )
        db.commit()
        publish({"type": "event", "accepted": False, "reason": reject.code.value if reject.code else "REJECTED", "event_id": event_id})
        lot = db.get(Lot, payload.lot_id) if payload.lot_id else None
        return False, reject.code.value if reject.code else "REJECTED", alarms, lot.status if lot else None

    lot = db.get(Lot, payload.lot_id)
    panel = db.get(Panel, payload.panel_id)
    assert lot is not None and panel is not None and equipment is not None
    assert step is not None

    recipe_fk = payload.recipe_id if payload.recipe_id and db.get(Recipe, payload.recipe_id) else None

    process_event = ProcessEvent(
        event_id=event_id,
        request_id=request_id,
        event_type=EventType.PROCESS.value,
        fingerprint=event_fingerprint(payload),
        equipment_id=equipment.id,
        lot_id=lot.id,
        panel_id=panel.id,
        recipe_id=recipe_fk,
        process_step=step,
        equipment_status=payload.equipment_status.value,
        cycle_time_sec=payload.cycle_time_sec,
        event_timestamp=as_naive_utc(payload.timestamp),
        received_at=utcnow(),
        inspect_result=payload.inspect_result,
    )
    db.add(process_event)
    db.flush()

    db.add(
        SensorReading(
            process_event_id=process_event.id,
            equipment_id=equipment.id,
            chamber_temperature=payload.chamber_temperature,
            vacuum_pressure=payload.vacuum_pressure,
            recorded_at=as_naive_utc(payload.timestamp),
        )
    )

    prev_eq = equipment.equipment_status
    equipment.equipment_status = payload.equipment_status.value
    equipment.current_lot_id = lot.id
    equipment.current_recipe_id = payload.recipe_id or lot.expected_recipe_id
    record_state_change(
        db,
        entity_type="EQUIPMENT",
        entity_id=equipment.id,
        from_status=prev_eq,
        to_status=equipment.equipment_status,
        reason=f"process {step}",
        event_id=event_id,
    )

    hold = False
    hold_reason = None
    for check in checks:
        if check.code is None:
            continue
        if check.severity and check.severity.value == "CRITICAL":
            logger.error("%s %s", check.code.value, check.message)
        else:
            logger.warning("%s %s", check.code.value, check.message)
        alarms.append(
            create_alarm(
                db,
                code=check.code,
                message=check.message,
                equipment_id=equipment.id,
                lot_id=lot.id,
                panel_id=panel.id,
                event_id=event_id,
                severity=check.severity,
            )
        )
        if check.hold_lot:
            hold = True
            hold_reason = check.code.value

    inspect_fail = (
        step == ProcessStep.INSPECT.value and payload.inspect_result == InspectResult.FAIL.value
    )
    if inspect_fail:
        hold = True
        hold_reason = AlarmCode.INSPECT_FAIL.value
        alarms.append(
            create_alarm(
                db,
                code=AlarmCode.INSPECT_FAIL,
                message=f"Glass {panel.id} INSPECT FAIL on {lot.product_type} lot {lot.id}",
                equipment_id=equipment.id,
                lot_id=lot.id,
                panel_id=panel.id,
                event_id=event_id,
            )
        )

    prev_lot = lot.status
    if hold:
        lot.status = LotStatus.HOLD.value
        lot.hold_reason = hold_reason
        panel.status = PanelStatus.FAIL.value if inspect_fail else PanelStatus.HOLD.value
        logger.error("LOT_HOLD lot=%s product=%s reason=%s", lot.id, lot.product_type, hold_reason)
    elif lot.status != LotStatus.HOLD.value:
        if step == ProcessStep.INSPECT.value:
            panel.status = PanelStatus.COMPLETE.value
            db.flush()
            if _lot_all_panels_complete(db, lot.id):
                lot.status = LotStatus.COMPLETE.value
                equipment.equipment_status = EquipmentStatus.IDLE.value
                logger.info("PROCESS_COMPLETE lot=%s product=%s glass=%s", lot.id, lot.product_type, panel.id)
            else:
                lot.status = LotStatus.PROCESSING.value
        else:
            lot.status = LotStatus.PROCESSING.value
            panel.status = PanelStatus.PROCESSING.value

    record_state_change(
        db,
        entity_type="LOT",
        entity_id=lot.id,
        from_status=prev_lot,
        to_status=lot.status,
        reason=hold_reason or step,
        event_id=event_id,
    )

    lot.current_equipment_id = equipment.id
    lot.current_step = step
    for other in (
        db.query(Equipment)
        .filter(Equipment.current_lot_id == lot.id, Equipment.id != equipment.id)
        .all()
    ):
        other.current_lot_id = None
    if lot.status == LotStatus.COMPLETE.value:
        equipment.current_lot_id = None
    refresh_work_order_for_lot(db, lot.id)

    write_event_log(db, event_id=event_id, request_id=request_id, payload=payload, accepted=True, reason=None)
    db.commit()
    db.refresh(lot)
    publish(
        {
            "type": "event",
            "accepted": True,
            "event_id": event_id,
            "equipment_id": equipment.id,
            "lot_id": lot.id,
            "product_type": lot.product_type,
            "process_step": step,
        }
    )
    return True, None, alarms, lot.status
