from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.enums import EventType
from app.schemas import EquipmentEventIn
from app.services.collector import collect_push
from app.services.history import panel_history
from app.services.timeutil import utcnow


def export_panel_events(db: Session, panel_id: str) -> list[dict]:
    rows = panel_history(db, panel_id)
    events = []
    for row in rows:
        events.append(
            {
                "equipment_id": row.equipment_id,
                "event_type": row.event_type or EventType.PROCESS.value,
                "lot_id": row.lot_id,
                "panel_id": row.panel_id,
                "process_step": row.process_step,
                "recipe_id": row.recipe_id,
                "equipment_status": row.equipment_status,
                "chamber_temperature": row.chamber_temperature,
                "vacuum_pressure": row.vacuum_pressure,
                "cycle_time_sec": row.cycle_time_sec,
                "inspect_result": row.inspect_result,
                "timestamp": row.event_timestamp.isoformat(),
            }
        )
    return events


def replay_events(
    db: Session,
    events: list[dict],
    *,
    refresh_timestamps: bool = True,
    lot_id: str | None = None,
    panel_id: str | None = None,
) -> dict:
    if not events:
        return {"ok": False, "error": "events가 비어 있다"}

    results = []
    for i, raw in enumerate(events):
        data = dict(raw)
        if lot_id:
            data["lot_id"] = lot_id
        if panel_id:
            data["panel_id"] = panel_id
        if refresh_timestamps:
            data["timestamp"] = (utcnow() + timedelta(seconds=i)).isoformat()
        payload = EquipmentEventIn(**data)
        event_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        accepted, reason, alarms, lot_status = collect_push(db, payload, request_id, event_id)
        results.append(
            {
                "accepted": accepted,
                "reason": reason,
                "lot_status": lot_status,
                "process_step": payload.process_step,
                "equipment_id": payload.equipment_id,
                "alarms": [a.alarm_code for a in alarms],
            }
        )
    return {
        "ok": True,
        "count": len(results),
        "accepted": sum(1 for r in results if r["accepted"]),
        "rejected": sum(1 for r in results if not r["accepted"]),
        "lot_id": lot_id or events[0].get("lot_id"),
        "panel_id": panel_id or events[0].get("panel_id"),
        "results": results,
    }
