"""중앙 상태/코드 정의. 문자열 리터럴을 여기저기에서 비교하지 않는다."""

from enum import Enum


class ProductType(str, Enum):
    OLED = "OLED"
    LCD = "LCD"


class EquipmentStatus(str, Enum):
    IDLE = "IDLE"
    RUN = "RUN"
    STOP = "STOP"
    ERROR = "ERROR"
    MAINTENANCE = "MAINTENANCE"


class ConnectionStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class LotStatus(str, Enum):
    WAIT = "WAIT"
    PROCESSING = "PROCESSING"
    HOLD = "HOLD"
    COMPLETE = "COMPLETE"


class PanelStatus(str, Enum):
    WAIT = "WAIT"
    PROCESSING = "PROCESSING"
    HOLD = "HOLD"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"
    SCRAP = "SCRAP"


class AlarmSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlarmCode(str, Enum):
    COMMUNICATION_LOSS = "COMMUNICATION_LOSS"
    TEMPERATURE_OUT_OF_RANGE = "TEMPERATURE_OUT_OF_RANGE"
    PRESSURE_OUT_OF_RANGE = "PRESSURE_OUT_OF_RANGE"
    RECIPE_MISMATCH = "RECIPE_MISMATCH"
    RECIPE_NOT_SELECTED = "RECIPE_NOT_SELECTED"
    INVALID_LOT = "INVALID_LOT"
    INVALID_PANEL = "INVALID_PANEL"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    STALE_TIMESTAMP = "STALE_TIMESTAMP"
    UNKNOWN_EQUIPMENT = "UNKNOWN_EQUIPMENT"
    DB_WRITE_FAILURE = "DB_WRITE_FAILURE"
    INTERLOCK_VIOLATION = "INTERLOCK_VIOLATION"
    STEP_SEQUENCE_VIOLATION = "STEP_SEQUENCE_VIOLATION"
    PRODUCT_ROUTE_VIOLATION = "PRODUCT_ROUTE_VIOLATION"
    EQUIPMENT_BUSY = "EQUIPMENT_BUSY"
    EQUIPMENT_MAINTENANCE = "EQUIPMENT_MAINTENANCE"
    EQUIPMENT_STOPPED = "EQUIPMENT_STOPPED"
    ILLEGAL_STATE_TRANSITION = "ILLEGAL_STATE_TRANSITION"
    INSPECT_FAIL = "INSPECT_FAIL"
    PANEL_SCRAPPED = "PANEL_SCRAPPED"


class ProcessStep(str, Enum):
    LOAD = "LOAD"
    CLEAN = "CLEAN"
    EVAP = "EVAP"
    ENCAP = "ENCAP"
    PI = "PI"
    LCD_CELL = "LCD_CELL"
    INSPECT = "INSPECT"
    # 구 MVP 호환. 내부에서는 EVAP로 정규화한다.
    DEPOSITION = "DEPOSITION"


class EventType(str, Enum):
    HEARTBEAT = "HEARTBEAT"
    PROCESS = "PROCESS"


class InterfaceType(str, Enum):
    SIMULATOR = "simulator"
    OPCUA = "opcua"
    MODBUS = "modbus"


class DowntimeReason(str, Enum):
    COMMUNICATION_LOSS = "COMMUNICATION_LOSS"
    STOP = "STOP"
    MAINTENANCE = "MAINTENANCE"
    ERROR = "ERROR"


class CommandType(str, Enum):
    HOLD_LOT = "HOLD_LOT"
    RELEASE_LOT = "RELEASE_LOT"
    MAINT_ENTER = "MAINT_ENTER"
    MAINT_EXIT = "MAINT_EXIT"
    ACK_ALARM = "ACK_ALARM"
    START = "START"
    STOP = "STOP"
    SELECT_RECIPE = "SELECT_RECIPE"
    SCRAP_PANEL = "SCRAP_PANEL"


class WorkOrderStatus(str, Enum):
    PLANNED = "PLANNED"
    RELEASED = "RELEASED"
    DONE = "DONE"


class CommandStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class InspectResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


ALARM_SEVERITY_BY_CODE = {
    AlarmCode.COMMUNICATION_LOSS: AlarmSeverity.CRITICAL,
    AlarmCode.TEMPERATURE_OUT_OF_RANGE: AlarmSeverity.WARNING,
    AlarmCode.PRESSURE_OUT_OF_RANGE: AlarmSeverity.WARNING,
    AlarmCode.RECIPE_MISMATCH: AlarmSeverity.CRITICAL,
    AlarmCode.RECIPE_NOT_SELECTED: AlarmSeverity.CRITICAL,
    AlarmCode.INVALID_LOT: AlarmSeverity.CRITICAL,
    AlarmCode.INVALID_PANEL: AlarmSeverity.CRITICAL,
    AlarmCode.DUPLICATE_EVENT: AlarmSeverity.WARNING,
    AlarmCode.STALE_TIMESTAMP: AlarmSeverity.WARNING,
    AlarmCode.UNKNOWN_EQUIPMENT: AlarmSeverity.CRITICAL,
    AlarmCode.DB_WRITE_FAILURE: AlarmSeverity.CRITICAL,
    AlarmCode.INTERLOCK_VIOLATION: AlarmSeverity.CRITICAL,
    AlarmCode.STEP_SEQUENCE_VIOLATION: AlarmSeverity.CRITICAL,
    AlarmCode.PRODUCT_ROUTE_VIOLATION: AlarmSeverity.CRITICAL,
    AlarmCode.EQUIPMENT_BUSY: AlarmSeverity.WARNING,
    AlarmCode.EQUIPMENT_MAINTENANCE: AlarmSeverity.WARNING,
    AlarmCode.EQUIPMENT_STOPPED: AlarmSeverity.WARNING,
    AlarmCode.ILLEGAL_STATE_TRANSITION: AlarmSeverity.WARNING,
    AlarmCode.INSPECT_FAIL: AlarmSeverity.CRITICAL,
    AlarmCode.PANEL_SCRAPPED: AlarmSeverity.WARNING,
}
