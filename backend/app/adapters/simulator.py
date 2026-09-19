"""현재 사용 중인 설비 경로: HTTP JSON push.

실제 송신은 simulator/python_simulator.py 와 csharp_simulator 가 한다.
이 클래스는 받은 프레임을 telemetry 테이블에 남기고, 호스트 DB에서 상태를 읽는다.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Equipment, Telemetry
from app.services.timeutil import as_naive_utc


class SimulatorAdapter:
    name = "simulator"
    transport = "HTTP/JSON"

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def connect(self) -> None:
        return None

    def read_status(self, equipment_id: str) -> dict[str, Any]:
        if self.db is None:
            return {"mode": "push", "equipment_id": equipment_id, "connected": False}
        eq = self.db.get(Equipment, equipment_id)
        if eq is None:
            return {"mode": "push", "equipment_id": equipment_id, "found": False}
        return {
            "mode": "push",
            "equipment_id": equipment_id,
            "equipment_status": eq.equipment_status,
            "connection_status": eq.connection_status,
            "interface_type": eq.interface_type,
            "interface_endpoint": eq.interface_endpoint,
            "last_seen_at": eq.last_seen_at.isoformat() if eq.last_seen_at else None,
        }

    def read_telemetry(self, equipment_id: str) -> dict[str, Any]:
        if self.db is None:
            return {"mode": "push", "equipment_id": equipment_id, "reading": None}
        row = (
            self.db.query(Telemetry)
            .filter(Telemetry.equipment_id == equipment_id)
            .order_by(Telemetry.recorded_at.desc(), Telemetry.id.desc())
            .first()
        )
        if row is None:
            return {"mode": "push", "equipment_id": equipment_id, "reading": None}
        return {
            "mode": "push",
            "equipment_id": equipment_id,
            "chamber_temperature": row.chamber_temperature,
            "vacuum_pressure": row.vacuum_pressure,
            "equipment_status": row.equipment_status,
            "source": row.source,
            "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
        }

    def send_command(
        self,
        equipment_id: str,
        command_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "mode": "host_db",
            "interface": self.name,
            "transport": self.transport,
            "equipment_id": equipment_id,
            "command_type": command_type,
            "payload": payload or {},
        }

    def accept_push(self, db: Session, payload: Any, event_id: str) -> dict[str, Any]:
        eq = db.get(Equipment, payload.equipment_id)
        if eq is None:
            return {"stored": False, "reason": "UNKNOWN_EQUIPMENT"}
        event_type = payload.event_type.value if hasattr(payload.event_type, "value") else str(payload.event_type)
        status = payload.equipment_status.value if hasattr(payload.equipment_status, "value") else str(payload.equipment_status)
        db.add(
            Telemetry(
                equipment_id=eq.id,
                source=event_type,
                interface_type=eq.interface_type or self.name,
                chamber_temperature=payload.chamber_temperature,
                vacuum_pressure=payload.vacuum_pressure,
                equipment_status=status,
                recorded_at=as_naive_utc(payload.timestamp),
                event_id=event_id,
            )
        )
        return {"stored": True, "source": event_type, "interface": self.name}

    def disconnect(self) -> None:
        return None
