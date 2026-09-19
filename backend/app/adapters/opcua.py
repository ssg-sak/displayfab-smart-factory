"""미래 OPC UA Adapter. 실제 서버/장비를 붙이지 않는다."""

from __future__ import annotations

from typing import Any


class OPCUAAdapter:
    name = "opcua"
    transport = "opc.tcp"

    def connect(self) -> None:
        raise NotImplementedError("P2: 실제 OPC UA 세션. 시뮬레이터를 대체하지 말고 옆에 둔다.")

    def read_status(self, equipment_id: str) -> dict[str, Any]:
        raise NotImplementedError("P2: OPC UA status node")

    def read_telemetry(self, equipment_id: str) -> dict[str, Any]:
        raise NotImplementedError("P2: OPC UA telemetry subscription → ingest_event")

    def send_command(
        self,
        equipment_id: str,
        command_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("P2: 사람이 MES에서 낸 명령만 설비로 내린다. Analytics 직접 제어 금지.")

    def accept_push(self, db: Any, payload: Any, event_id: str) -> dict[str, Any]:
        raise NotImplementedError("OPC UA 는 pull/subscribe. HTTP push 는 SimulatorAdapter.")

    def disconnect(self) -> None:
        raise NotImplementedError("P2")
