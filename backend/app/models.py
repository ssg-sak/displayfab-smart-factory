from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ConnectionStatus, EquipmentStatus, EventType, LotStatus, PanelStatus


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    process_step: Mapped[str] = mapped_column(String(32))
    product_scope: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    equipment_status: Mapped[str] = mapped_column(String(32), default=EquipmentStatus.IDLE.value)
    connection_status: Mapped[str] = mapped_column(String(32), default=ConnectionStatus.OFFLINE.value)
    current_lot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    current_recipe_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    interface_type: Mapped[str] = mapped_column(String(32), default="simulator")
    interface_endpoint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    process_events: Mapped[list["ProcessEvent"]] = relationship(back_populates="equipment")
    alarms: Mapped[list["Alarm"]] = relationship(back_populates="equipment")
    telemetry: Mapped[list["Telemetry"]] = relationship(back_populates="equipment")
    downtime: Mapped[list["EquipmentDowntime"]] = relationship(back_populates="equipment")


class Recipe(Base):
    __tablename__ = "recipe"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    product_type: Mapped[str] = mapped_column(String(16))
    expected_temperature_min: Mapped[float] = mapped_column(Float)
    expected_temperature_max: Mapped[float] = mapped_column(Float)
    expected_pressure_min: Mapped[float] = mapped_column(Float)
    expected_pressure_max: Mapped[float] = mapped_column(Float)

    lots: Mapped[list["Lot"]] = relationship(back_populates="expected_recipe")
    process_events: Mapped[list["ProcessEvent"]] = relationship(back_populates="recipe")


class Lot(Base):
    __tablename__ = "lot"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cassette_id: Mapped[str] = mapped_column(String(64), index=True)
    product_type: Mapped[str] = mapped_column(String(16), index=True)
    expected_recipe_id: Mapped[str] = mapped_column(ForeignKey("recipe.id"))
    status: Mapped[str] = mapped_column(String(32), default=LotStatus.WAIT.value)
    current_equipment_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    hold_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    expected_recipe: Mapped[Recipe] = relationship(back_populates="lots")
    panels: Mapped[list["Panel"]] = relationship(back_populates="lot")
    process_events: Mapped[list["ProcessEvent"]] = relationship(back_populates="lot")


class Panel(Base):
    __tablename__ = "panel"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lot.id"))
    slot_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default=PanelStatus.WAIT.value)

    lot: Mapped[Lot] = relationship(back_populates="panels")
    process_events: Mapped[list["ProcessEvent"]] = relationship(back_populates="panel")


class ProcessEvent(Base):
    __tablename__ = "process_event"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_process_event_fingerprint"),
        Index("ix_process_event_equipment_ts", "equipment_id", "event_timestamp"),
        Index("ix_process_event_lot_ts", "lot_id", "event_timestamp"),
        Index("ix_process_event_panel_ts", "panel_id", "event_timestamp"),
        Index("ix_process_event_timestamp", "event_timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), default=EventType.PROCESS.value)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id"))
    lot_id: Mapped[str] = mapped_column(ForeignKey("lot.id"))
    panel_id: Mapped[str] = mapped_column(ForeignKey("panel.id"))
    recipe_id: Mapped[Optional[str]] = mapped_column(ForeignKey("recipe.id"), nullable=True)
    process_step: Mapped[str] = mapped_column(String(32))
    equipment_status: Mapped[str] = mapped_column(String(32))
    cycle_time_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime)
    inspect_result: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    equipment: Mapped[Equipment] = relationship(back_populates="process_events")
    lot: Mapped[Lot] = relationship(back_populates="process_events")
    panel: Mapped[Panel] = relationship(back_populates="process_events")
    recipe: Mapped[Optional[Recipe]] = relationship(back_populates="process_events")
    sensor_reading: Mapped[Optional["SensorReading"]] = relationship(
        back_populates="process_event", uselist=False
    )


class SensorReading(Base):
    __tablename__ = "sensor_reading"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    process_event_id: Mapped[int] = mapped_column(ForeignKey("process_event.id"), unique=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id"), index=True)
    chamber_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vacuum_pressure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime)

    process_event: Mapped[ProcessEvent] = relationship(back_populates="sensor_reading")


class Telemetry(Base):
    """인터페이스 계층 시계열. PROCESS의 SensorReading과 별개다."""

    __tablename__ = "telemetry"
    __table_args__ = (Index("ix_telemetry_equipment_ts", "equipment_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id"), index=True)
    source: Mapped[str] = mapped_column(String(32))
    interface_type: Mapped[str] = mapped_column(String(32), default="simulator")
    chamber_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vacuum_pressure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    equipment_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    equipment: Mapped["Equipment"] = relationship(back_populates="telemetry")


class EquipmentDowntime(Base):
    """통신 끊김·정지·정비 구간. OEE Availability 계산용."""

    __tablename__ = "equipment_downtime"
    __table_args__ = (Index("ix_downtime_equipment_start", "equipment_id", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id"), index=True)
    reason: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    equipment: Mapped["Equipment"] = relationship(back_populates="downtime")


class Alarm(Base):
    __tablename__ = "alarm"
    __table_args__ = (
        Index("ix_alarm_equipment_time", "equipment_id", "occurred_at"),
        Index("ix_alarm_code", "alarm_code"),
        Index("ix_alarm_lot", "lot_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alarm_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    equipment_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("equipment.id"), nullable=True
    )
    lot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    panel_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    alarm_code: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    equipment: Mapped[Optional[Equipment]] = relationship(back_populates="alarms")


class EventLog(Base):
    __tablename__ = "event_log"
    __table_args__ = (Index("ix_event_log_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), index=True)
    request_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    accepted: Mapped[bool] = mapped_column()
    reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    equipment_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    lot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    panel_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    process_step: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class StateChange(Base):
    __tablename__ = "state_change"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(255))
    event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime)


class HostCommand(Base):
    __tablename__ = "host_command"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command_id: Mapped[str] = mapped_column(String(36), unique=True)
    command_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    equipment_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    lot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    alarm_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(String(500))
    requested_by: Mapped[str] = mapped_column(String(64), default="operator")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    interface_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class WorkOrder(Base):
    __tablename__ = "work_order"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_type: Mapped[str] = mapped_column(String(16), index=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipe.id"))
    qty: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="RELEASED")
    lot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cassette_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
