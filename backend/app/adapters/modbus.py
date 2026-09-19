"""미래 Modbus Adapter. 실제 장비를 붙이지 않는다."""

from __future__ import annotations

from typing import Any


class ModbusAdapter:
    name = "modbus"
    transport = "modbus-tcp"

    def connect(self) -> None:
        raise NotImplementedError("P2: 실제 Modbus TCP/RTU. Siemens/Mitsubishi 장비가 있는 척하지 말 것.")

    def read_status(self, equipment_id: str) -> dict[str, Any]:
        raise NotImplementedError("P2")

    def read_telemetry(self, equipment_id: str) -> dict[str, Any]:
        raise NotImplementedError("P2")

    def send_command(
        self,
        equipment_id: str,
        command_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("P2")

    def accept_push(self, db: Any, payload: Any, event_id: str) -> dict[str, Any]:
        raise NotImplementedError("Modbus 는 poll. HTTP push 는 SimulatorAdapter.")

    def disconnect(self) -> None:
        raise NotImplementedError("P2")
