"""설비 통신 계약.

호스트는 설비를 직접 OPC/Modbus로 부르지 않는다.
현재 HTTP JSON push 는 SimulatorAdapter.accept_push.
나중에 Collector가 Adapter.read_telemetry 로 읽어 ingest 한다 (pull).
"""

from __future__ import annotations

from typing import Any, Protocol


class EquipmentAdapter(Protocol):
    name: str

    def connect(self) -> None: ...

    def read_status(self, equipment_id: str) -> dict[str, Any]: ...

    def read_telemetry(self, equipment_id: str) -> dict[str, Any]: ...

    def send_command(
        self,
        equipment_id: str,
        command_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def accept_push(self, db: Any, payload: Any, event_id: str) -> dict[str, Any]: ...

    def disconnect(self) -> None: ...
