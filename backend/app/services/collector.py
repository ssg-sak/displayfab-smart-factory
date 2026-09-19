"""인터페이스 수집기.

현재: Simulator HTTP push → telemetry 저장 → ingest_event
미래: Adapter.read_telemetry (OPC UA/Modbus) → 같은 ingest_event
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.adapters.simulator import SimulatorAdapter
from app.schemas import EquipmentEventIn
from app.services.event_ingestion import ingest_event


def collect_push(
    db: Session,
    payload: EquipmentEventIn,
    request_id: str,
    event_id: str,
) -> tuple[bool, str | None, list, str | None]:
    if not payload.force_db_failure:
        SimulatorAdapter(db).accept_push(db, payload, event_id)
    return ingest_event(db, payload, request_id, event_id)
