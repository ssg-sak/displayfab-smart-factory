from __future__ import annotations

from sqlalchemy.orm import Session

from app.adapters.base import EquipmentAdapter
from app.adapters.modbus import ModbusAdapter
from app.adapters.opcua import OPCUAAdapter
from app.adapters.simulator import SimulatorAdapter
from app.enums import InterfaceType


def get_adapter(interface_type: str | None, db: Session | None = None) -> EquipmentAdapter:
    kind = (interface_type or InterfaceType.SIMULATOR.value).lower()
    if kind == InterfaceType.OPCUA.value:
        return OPCUAAdapter()
    if kind == InterfaceType.MODBUS.value:
        return ModbusAdapter()
    return SimulatorAdapter(db)
