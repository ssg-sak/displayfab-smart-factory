from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.adapters.registry import get_adapter
from app.enums import (
    AlarmCode,
    CommandStatus,
    CommandType,
    DowntimeReason,
    EquipmentStatus,
    LotStatus,
    PanelStatus,
)
from app.logging_setup import get_logger
from app.models import Alarm, Equipment, HostCommand, Lot, Panel
from app.schemas import CommandIn
from app.services.downtime import close_downtime, open_downtime
from app.services.work_orders import refresh_work_order_for_lot
from app.services.event_bus import publish
from app.services.state_change import record_state_change
from app.services.timeutil import utcnow

logger = get_logger(__name__)


def execute_command(db: Session, payload: CommandIn) -> HostCommand:
    command_id = str(uuid.uuid4())
    now = utcnow()
    cmd_type = payload.command_type.value

    def save(status: str, message: str) -> HostCommand:
        row = HostCommand(
            command_id=command_id,
            command_type=cmd_type,
            status=status,
            equipment_id=payload.equipment_id,
            lot_id=payload.lot_id,
            alarm_id=payload.alarm_id,
            message=message,
            requested_by=payload.requested_by,
            created_at=now,
        )
        if status == CommandStatus.ACCEPTED.value and payload.equipment_id:
            eq = db.get(Equipment, payload.equipment_id)
            adapter = get_adapter(eq.interface_type if eq else None, db)
            try:
                adapter.send_command(
                    payload.equipment_id,
                    cmd_type,
                    {
                        "lot_id": payload.lot_id,
                        "recipe_id": payload.recipe_id,
                        "alarm_id": payload.alarm_id,
                        "panel_id": payload.panel_id,
                    },
                )
                row.interface_type = adapter.name
                row.delivered_at = now
            except NotImplementedError:
                row.interface_type = eq.interface_type if eq else None
        db.add(row)
        db.commit()
        db.refresh(row)
        publish({"type": "command", "command_type": cmd_type, "status": status, "message": message})
        return row

    if cmd_type == CommandType.HOLD_LOT.value:
        lot = db.get(Lot, payload.lot_id) if payload.lot_id else None
        if lot is None:
            return save(CommandStatus.REJECTED.value, "작업이 없습니다")
        if lot.status == LotStatus.COMPLETE.value:
            return save(CommandStatus.REJECTED.value, "끝난 작업은 멈출 수 없습니다")
        prev = lot.status
        lot.status = LotStatus.HOLD.value
        lot.hold_reason = "HOST_HOLD"
        record_state_change(db, entity_type="LOT", entity_id=lot.id, from_status=prev, to_status=lot.status, reason="HOST_HOLD")
        logger.error("HOST_HOLD lot=%s product=%s", lot.id, lot.product_type)
        return save(CommandStatus.ACCEPTED.value, f"{lot.id} 호스트가 멈춤")

    if cmd_type == CommandType.RELEASE_LOT.value:
        lot = db.get(Lot, payload.lot_id) if payload.lot_id else None
        if lot is None:
            return save(CommandStatus.REJECTED.value, "작업이 없습니다")
        if lot.status != LotStatus.HOLD.value:
            return save(CommandStatus.REJECTED.value, f"지금 {lot.status} 상태라 다시 보낼 수 없습니다")
        prev = lot.status
        has_event = lot.current_step is not None
        lot.status = LotStatus.PROCESSING.value if has_event else LotStatus.WAIT.value
        lot.hold_reason = None
        for panel in db.query(Panel).filter(Panel.lot_id == lot.id, Panel.status == PanelStatus.HOLD.value):
            panel.status = PanelStatus.PROCESSING.value if has_event else PanelStatus.WAIT.value
        record_state_change(db, entity_type="LOT", entity_id=lot.id, from_status=prev, to_status=lot.status, reason="HOST_RELEASE")
        logger.info("HOST_RELEASE lot=%s", lot.id)
        return save(CommandStatus.ACCEPTED.value, f"{lot.id} 다시 보냄")

    if cmd_type == CommandType.MAINT_ENTER.value:
        eq = db.get(Equipment, payload.equipment_id) if payload.equipment_id else None
        if eq is None:
            return save(CommandStatus.REJECTED.value, "설비가 없습니다")
        prev = eq.equipment_status
        eq.equipment_status = EquipmentStatus.MAINTENANCE.value
        record_state_change(db, entity_type="EQUIPMENT", entity_id=eq.id, from_status=prev, to_status=eq.equipment_status, reason="MAINT_ENTER")
        open_downtime(db, eq.id, DowntimeReason.MAINTENANCE.value)
        return save(CommandStatus.ACCEPTED.value, f"{eq.id} 정비 시작")

    if cmd_type == CommandType.MAINT_EXIT.value:
        eq = db.get(Equipment, payload.equipment_id) if payload.equipment_id else None
        if eq is None:
            return save(CommandStatus.REJECTED.value, "설비가 없습니다")
        if eq.equipment_status != EquipmentStatus.MAINTENANCE.value:
            return save(CommandStatus.REJECTED.value, f"{eq.id} 은 정비 중이 아닙니다")
        prev = eq.equipment_status
        eq.equipment_status = EquipmentStatus.IDLE.value
        record_state_change(db, entity_type="EQUIPMENT", entity_id=eq.id, from_status=prev, to_status=eq.equipment_status, reason="MAINT_EXIT")
        close_downtime(db, eq.id, reasons=[DowntimeReason.MAINTENANCE.value])
        return save(CommandStatus.ACCEPTED.value, f"{eq.id} 정비 끝 · 대기")

    if cmd_type in (CommandType.START.value, CommandType.STOP.value):
        eq = db.get(Equipment, payload.equipment_id) if payload.equipment_id else None
        if eq is None:
            return save(CommandStatus.REJECTED.value, "설비가 없습니다")
        if eq.equipment_status == EquipmentStatus.MAINTENANCE.value:
            return save(CommandStatus.REJECTED.value, "정비 중에는 켜거나 끌 수 없습니다")
        prev = eq.equipment_status
        eq.equipment_status = EquipmentStatus.RUN.value if cmd_type == CommandType.START.value else EquipmentStatus.STOP.value
        record_state_change(db, entity_type="EQUIPMENT", entity_id=eq.id, from_status=prev, to_status=eq.equipment_status, reason=cmd_type)
        if cmd_type == CommandType.START.value:
            close_downtime(db, eq.id, reasons=[DowntimeReason.STOP.value])
        else:
            open_downtime(db, eq.id, DowntimeReason.STOP.value)
        started = "켰습니다" if cmd_type == CommandType.START.value else "껐습니다"
        return save(CommandStatus.ACCEPTED.value, f"{eq.id} {started}")

    if cmd_type == CommandType.SELECT_RECIPE.value:
        eq = db.get(Equipment, payload.equipment_id) if payload.equipment_id else None
        if eq is None:
            return save(CommandStatus.REJECTED.value, "설비가 없습니다")
        from app.models import Recipe as RecipeModel

        if not payload.recipe_id:
            return save(CommandStatus.REJECTED.value, "조건을 고르세요")
        recipe = db.get(RecipeModel, payload.recipe_id)
        if recipe is None:
            return save(CommandStatus.REJECTED.value, f"없는 조건: {payload.recipe_id}")
        if eq.product_scope and eq.product_scope != recipe.product_type:
            return save(CommandStatus.REJECTED.value, f"{eq.id} 제품과 조건이 다릅니다")
        prev = eq.current_recipe_id
        eq.current_recipe_id = payload.recipe_id
        record_state_change(
            db,
            entity_type="EQUIPMENT",
            entity_id=eq.id,
            from_status=prev,
            to_status=payload.recipe_id,
            reason="SELECT_RECIPE",
        )
        return save(CommandStatus.ACCEPTED.value, f"{eq.id} 조건 {payload.recipe_id}")

    if cmd_type == CommandType.ACK_ALARM.value:
        alarm = db.query(Alarm).filter(Alarm.alarm_id == payload.alarm_id).first() if payload.alarm_id else None
        if alarm is None:
            return save(CommandStatus.REJECTED.value, "알람이 없습니다")
        alarm.acknowledged_at = now
        alarm.acknowledged_by = payload.requested_by
        if alarm.alarm_code != AlarmCode.COMMUNICATION_LOSS.value:
            alarm.resolved_at = now
        return save(CommandStatus.ACCEPTED.value, f"{alarm.alarm_id} 확인함")

    if cmd_type == CommandType.SCRAP_PANEL.value:
        panel = db.get(Panel, payload.panel_id) if payload.panel_id else None
        if panel is None:
            return save(CommandStatus.REJECTED.value, "유리가 없습니다")
        if panel.status == PanelStatus.SCRAP.value:
            return save(CommandStatus.REJECTED.value, f"{panel.id} 이미 버린 유리입니다")
        if panel.status == PanelStatus.COMPLETE.value:
            return save(CommandStatus.REJECTED.value, f"{panel.id} 이미 끝났습니다")
        prev = panel.status
        panel.status = PanelStatus.SCRAP.value
        payload.lot_id = panel.lot_id
        record_state_change(
            db,
            entity_type="PANEL",
            entity_id=panel.id,
            from_status=prev,
            to_status=panel.status,
            reason="SCRAP",
        )
        logger.error("PANEL_SCRAP glass=%s lot=%s", panel.id, panel.lot_id)
        refresh_work_order_for_lot(db, panel.lot_id)
        return save(CommandStatus.ACCEPTED.value, f"{panel.id} 폐기")

    return save(CommandStatus.REJECTED.value, f"없는 명령 {cmd_type}")
