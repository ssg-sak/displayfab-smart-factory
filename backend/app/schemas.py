from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.enums import (
    AlarmSeverity,
    CommandType,
    ConnectionStatus,
    EquipmentStatus,
    EventType,
    LotStatus,
)


class EquipmentEventIn(BaseModel):
    equipment_id: str
    event_type: EventType = EventType.PROCESS
    lot_id: Optional[str] = None
    panel_id: Optional[str] = None
    process_step: Optional[str] = None
    recipe_id: Optional[str] = None
    equipment_status: EquipmentStatus = EquipmentStatus.RUN
    chamber_temperature: Optional[float] = None
    vacuum_pressure: Optional[float] = None
    cycle_time_sec: Optional[float] = None
    alarm_code: Optional[str] = None
    timestamp: datetime
    inspect_result: Optional[str] = None
    force_db_failure: bool = False


class AlarmOut(BaseModel):
    alarm_id: str
    equipment_id: Optional[str]
    lot_id: Optional[str]
    panel_id: Optional[str] = None
    alarm_code: str
    severity: AlarmSeverity | str
    message: str
    occurred_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    event_id: Optional[str] = None

    model_config = {"from_attributes": True}


class EventIngestOut(BaseModel):
    accepted: bool
    event_id: str
    request_id: str
    reason: Optional[str] = None
    lot_status: Optional[str] = None
    next_step: Optional[str] = None
    next_equipment_id: Optional[str] = None
    alarms: list[AlarmOut] = Field(default_factory=list)


class EquipmentOut(BaseModel):
    id: str
    name: str
    process_step: str
    product_scope: Optional[str]
    equipment_status: EquipmentStatus | str
    connection_status: ConnectionStatus | str
    current_lot_id: Optional[str]
    current_recipe_id: Optional[str]
    last_seen_at: Optional[datetime]
    interface_type: str = "simulator"
    interface_endpoint: Optional[str] = None
    open_alarm_count: int = 0

    model_config = {"from_attributes": True}


class LotOut(BaseModel):
    id: str
    cassette_id: str
    product_type: str
    expected_recipe_id: str
    status: LotStatus | str
    current_equipment_id: Optional[str]
    current_step: Optional[str]
    hold_reason: Optional[str] = None
    panel_count: int = 0

    model_config = {"from_attributes": True}


class ProcessHistoryItem(BaseModel):
    event_id: str
    event_type: str = "PROCESS"
    equipment_id: str
    lot_id: str
    panel_id: str
    process_step: str
    recipe_id: Optional[str]
    equipment_status: str
    cycle_time_sec: Optional[float]
    chamber_temperature: Optional[float] = None
    vacuum_pressure: Optional[float] = None
    inspect_result: Optional[str] = None
    event_timestamp: datetime
    received_at: datetime


class EventLogOut(BaseModel):
    event_id: str
    request_id: str
    event_type: str
    accepted: bool
    reason: Optional[str]
    equipment_id: Optional[str]
    lot_id: Optional[str]
    panel_id: Optional[str]
    process_step: Optional[str]
    summary: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CommandIn(BaseModel):
    command_type: CommandType
    equipment_id: Optional[str] = None
    lot_id: Optional[str] = None
    alarm_id: Optional[str] = None
    panel_id: Optional[str] = None
    recipe_id: Optional[str] = None
    requested_by: str = "operator"


class CommandOut(BaseModel):
    command_id: str
    command_type: str
    status: str
    equipment_id: Optional[str]
    lot_id: Optional[str]
    alarm_id: Optional[str]
    message: str
    created_at: datetime
    interface_type: Optional[str] = None
    delivered_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DiagnosisOut(BaseModel):
    lot_id: str
    cassette_id: str
    product_type: str
    status: str
    hold_reason: Optional[str]
    route: list[str]
    current_step: Optional[str]
    current_equipment_id: Optional[str]
    open_alarms: list[AlarmOut]
    last_events: list[str]
    next_checks: list[str]
    summary: str = ""
    action: str = ""


class KpiOut(BaseModel):
    equipment_online: int
    equipment_offline: int
    lots_hold: int
    lots_processing: int
    open_alarms: int
    events_last_5min: int
    oled_lots: int
    lcd_lots: int
    inspect_pass: int = 0
    inspect_fail: int = 0
    inspect_scrap: int = 0
    yield_pct: Optional[float] = None
    yield_by_equipment: list["YieldByEquipmentOut"] = Field(default_factory=list)


class YieldByEquipmentOut(BaseModel):
    equipment_id: str
    complete: int
    fail: int
    yield_pct: Optional[float] = None


class TelemetryOut(BaseModel):
    equipment_id: str
    source: str
    interface_type: str
    chamber_temperature: Optional[float] = None
    vacuum_pressure: Optional[float] = None
    equipment_status: Optional[str] = None
    recorded_at: datetime
    event_id: Optional[str] = None

    model_config = {"from_attributes": True}


class DowntimeOut(BaseModel):
    equipment_id: str
    reason: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_sec: Optional[float] = None

    model_config = {"from_attributes": True}


class EquipmentInterfaceBriefOut(BaseModel):
    equipment_id: str
    interface_type: str
    transport: Optional[str] = None
    connection_status: str
    last_seen_at: Optional[datetime] = None
    chamber_temperature: Optional[float] = None
    vacuum_pressure: Optional[float] = None
    recorded_at: Optional[datetime] = None
    telemetry_count: int = 0
    downtime_sec_today: float = 0.0
    open_downtime_reason: Optional[str] = None


class EquipmentOeeOut(BaseModel):
    equipment_id: str
    processed: int
    good: int
    bad: int
    planned_sec: float
    downtime_sec: float
    operating_sec: float
    ideal_runtime_sec: float
    availability: Optional[float] = None
    performance: Optional[float] = None
    quality: Optional[float] = None
    oee: Optional[float] = None


class OeeOut(BaseModel):
    date: str
    planned_basis: str
    planned_sec: float
    availability: Optional[float] = None
    performance: Optional[float] = None
    quality: Optional[float] = None
    oee: Optional[float] = None
    good: int
    bad: int
    note: str
    missing: list[str] = Field(default_factory=list)
    equipment: list[EquipmentOeeOut] = Field(default_factory=list)


class AnomalyScoreOut(BaseModel):
    latest: float
    mean: float
    stdev: Optional[float] = None
    sigma: Optional[float] = None
    level: str


class EquipmentAnomalyOut(BaseModel):
    equipment_id: str
    samples: int
    level: str
    temperature: Optional[AnomalyScoreOut] = None
    pressure: Optional[AnomalyScoreOut] = None


class AnomalyOut(BaseModel):
    date: str
    method: str
    note: str
    flagged: list[str] = Field(default_factory=list)
    equipment: list[EquipmentAnomalyOut] = Field(default_factory=list)


class EquipmentInterfaceOut(BaseModel):
    equipment_id: str
    interface_type: str
    interface_endpoint: Optional[str] = None
    adapter: str
    transport: Optional[str] = None
    poll_implemented: bool
    connection_status: str
    equipment_status: str
    last_seen_at: Optional[datetime] = None
    last_telemetry: Optional[TelemetryOut] = None
    open_downtime: list[DowntimeOut] = Field(default_factory=list)


class SlotOut(BaseModel):
    slot_no: int
    panel_id: str
    status: str


class SlotMapOut(BaseModel):
    lot_id: str
    cassette_id: str
    product_type: str
    recipe_id: str
    status: str
    slots: list[SlotOut]


class TravelerSlotOut(BaseModel):
    slot_no: int
    panel_id: str
    status: str
    last_step: Optional[str] = None
    last_equipment_id: Optional[str] = None
    last_at: Optional[datetime] = None


class TravelerOut(BaseModel):
    lot_id: str
    cassette_id: str
    product_type: str
    recipe_id: str
    status: str
    hold_reason: Optional[str] = None
    current_step: Optional[str] = None
    current_equipment_id: Optional[str] = None
    slots: list[TravelerSlotOut]


class LineOut(BaseModel):
    oled_route: list[str]
    lcd_route: list[str]
    oled_equipment: list[str] = []
    lcd_equipment: list[str] = []
    note: str


class ProductProgressOut(BaseModel):
    target: int
    complete: int
    fail: int
    scrap: int
    hold_lots: int


class CloseoutOut(BaseModel):
    target: int
    complete: int
    fail: int
    scrap: int
    remaining: int
    hold_lots: int
    offline: int
    yield_pct: Optional[float] = None
    line: str


class ProductionOut(BaseModel):
    date: str
    oled: ProductProgressOut
    lcd: ProductProgressOut
    hold_lots: list[str]
    offline_equipment: list[str]
    open_alarms: int
    summary: str
    blocked: str
    closeout: Optional[CloseoutOut] = None


class HealthOut(BaseModel):
    status: str
    db: str
    equipment_online: int
    equipment_offline: int
    open_alarms: int
    demo_autopilot: bool = False


class ReplayIn(BaseModel):
    events: list[dict]
    refresh_timestamps: bool = True
    lot_id: Optional[str] = None
    panel_id: Optional[str] = None


class DispatchOut(BaseModel):
    panel_id: str
    lot_id: str
    cassette_id: str
    product_type: str
    recipe_id: str
    lot_status: str
    panel_status: str
    last_step: Optional[str] = None
    next_step: Optional[str] = None
    next_equipment_id: Optional[str] = None
    at_equipment_id: Optional[str] = None
    done: bool = False


class CassetteWipOut(BaseModel):
    lot_id: str
    cassette_id: str
    product_type: str
    status: str
    at_equipment_id: Optional[str] = None
    next_step: Optional[str] = None


class WipOut(BaseModel):
    by_step: dict[str, int]
    complete: int
    fail: int = 0
    scrap: int = 0
    cassettes: list[CassetteWipOut]


class WorkOrderIn(BaseModel):
    product_type: str
    recipe_id: Optional[str] = None
    qty: int = Field(default=3, ge=1, le=10)


class WorkOrderOut(BaseModel):
    id: str
    product_type: str
    recipe_id: str
    qty: int
    status: str
    lot_id: Optional[str] = None
    cassette_id: Optional[str] = None
    panel_ids: list[str] = Field(default_factory=list)
    complete: int = 0
    fail: int = 0
    scrap: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class MesStepOut(BaseModel):
    step: str
    done: int
    total: int
    state: str


class MesLotOut(BaseModel):
    lot_id: str
    cassette_id: str
    product_type: str
    recipe_id: str
    status: str
    hold_reason: Optional[str] = None
    current_step: Optional[str] = None
    current_equipment_id: Optional[str] = None
    qty: int
    complete: int
    fail: int
    scrap: int
    route: list[MesStepOut]
    next_step: Optional[str] = None
    next_equipment_id: Optional[str] = None


class MesEquipmentOut(BaseModel):
    id: str
    process_step: str
    product_scope: Optional[str] = None
    equipment_status: str
    connection_status: str
    current_lot_id: Optional[str] = None
    current_recipe_id: Optional[str] = None


class MesOrderOut(BaseModel):
    id: str
    product_type: str
    recipe_id: str
    qty: int
    status: str
    lot_id: Optional[str] = None
    cassette_id: Optional[str] = None
    complete: int
    fail: int
    scrap: int


class MesBoardOut(BaseModel):
    note: str
    waiting_glass: int = 0
    equipment_offline: int = 0
    orders: list[MesOrderOut]
    lots: list[MesLotOut]
    equipment: list[MesEquipmentOut]
    holds: list[MesLotOut]
    production: dict
