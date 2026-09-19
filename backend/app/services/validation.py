from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.rules import (
    EQUIPMENT_PRODUCT,
    EQUIPMENT_STEP,
    allowed_next_steps,
    normalize_step,
)
from app.enums import (
    AlarmCode,
    AlarmSeverity,
    ConnectionStatus,
    EquipmentStatus,
    EventType,
    LotStatus,
    PanelStatus,
    ProcessStep,
)
from app.models import Equipment, Lot, Panel, ProcessEvent, Recipe
from app.schemas import EquipmentEventIn
from app.services.fingerprint import event_fingerprint
from app.services.timeutil import as_naive_utc, utcnow
from app.config import settings


class CheckResult:
    def __init__(
        self,
        reject: bool,
        code: AlarmCode | None = None,
        message: str = "",
        severity: AlarmSeverity | None = None,
        hold_lot: bool = False,
    ) -> None:
        self.reject = reject
        self.code = code
        self.message = message
        self.severity = severity
        self.hold_lot = hold_lot


def _temperature_severity(value: float, recipe: Recipe) -> AlarmSeverity:
    span = recipe.expected_temperature_max - recipe.expected_temperature_min
    low = recipe.expected_temperature_min - span * settings.sensor_critical_deviation_ratio
    high = recipe.expected_temperature_max + span * settings.sensor_critical_deviation_ratio
    if value < low or value > high:
        return AlarmSeverity.CRITICAL
    return AlarmSeverity.WARNING


def _pressure_severity(value: float, recipe: Recipe) -> AlarmSeverity:
    span = recipe.expected_pressure_max - recipe.expected_pressure_min
    low = recipe.expected_pressure_min - span * settings.sensor_critical_deviation_ratio
    high = recipe.expected_pressure_max + span * settings.sensor_critical_deviation_ratio
    if value < low or value > high:
        return AlarmSeverity.CRITICAL
    return AlarmSeverity.WARNING


def _last_step(db: Session, panel_id: str) -> str | None:
    row = (
        db.query(ProcessEvent)
        .filter(ProcessEvent.panel_id == panel_id)
        .order_by(ProcessEvent.event_timestamp.desc(), ProcessEvent.id.desc())
        .first()
    )
    return normalize_step(row.process_step) if row else None


def validate_event(db: Session, payload: EquipmentEventIn) -> list[CheckResult]:
    results: list[CheckResult] = []
    event_type = payload.event_type.value if hasattr(payload.event_type, "value") else str(payload.event_type)
    step = normalize_step(payload.process_step)

    equipment = db.get(Equipment, payload.equipment_id)
    if equipment is None:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.UNKNOWN_EQUIPMENT,
                message=f"Unknown equipment_id={payload.equipment_id}",
            )
        ]

    event_ts = as_naive_utc(payload.timestamp)
    now = utcnow()
    age = (now - event_ts).total_seconds()
    if age > settings.stale_event_threshold_sec:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.STALE_TIMESTAMP,
                message=f"Event timestamp is {int(age)}s old (limit {settings.stale_event_threshold_sec}s)",
            )
        ]
    if age < -settings.future_event_tolerance_sec:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.STALE_TIMESTAMP,
                message="Event timestamp is too far in the future",
            )
        ]

    if event_type == EventType.HEARTBEAT.value:
        return []

    fingerprint = event_fingerprint(payload)
    duplicate = db.query(ProcessEvent).filter(ProcessEvent.fingerprint == fingerprint).first()
    if duplicate is not None:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.DUPLICATE_EVENT,
                message="Duplicate process event received",
            )
        ]

    if not payload.lot_id or not payload.panel_id or not step:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.INVALID_LOT,
                message="PROCESS event requires lot_id, panel_id, process_step",
            )
        ]

    if (
        equipment.connection_status == ConnectionStatus.OFFLINE.value
        and equipment.last_seen_at is not None
    ):
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.COMMUNICATION_LOSS,
                message=f"{equipment.id} is OFFLINE; heartbeat required before PROCESS",
            )
        ]

    if equipment.equipment_status == EquipmentStatus.MAINTENANCE.value:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.EQUIPMENT_MAINTENANCE,
                message=f"{equipment.id} is in MAINTENANCE",
            )
        ]

    if equipment.equipment_status in (EquipmentStatus.IDLE.value, EquipmentStatus.STOP.value, EquipmentStatus.ERROR.value):
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.EQUIPMENT_STOPPED,
                message=f"{equipment.id} is {equipment.equipment_status}; host START required before PROCESS",
            )
        ]

    expected_eq_step = EQUIPMENT_STEP.get(equipment.id)
    if expected_eq_step and step != expected_eq_step:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.INTERLOCK_VIOLATION,
                message=f"{equipment.id} accepts {expected_eq_step} but received {step}",
            )
        ]

    lot = db.get(Lot, payload.lot_id)
    if lot is None:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.INVALID_LOT,
                message=f"Unknown lot_id={payload.lot_id}",
            )
        ]

    panel = db.get(Panel, payload.panel_id)
    if panel is None or panel.lot_id != lot.id:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.INVALID_PANEL,
                message=f"Glass {payload.panel_id} does not belong to cassette/lot {payload.lot_id}",
            )
        ]

    if panel.status == PanelStatus.SCRAP.value:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.PANEL_SCRAPPED,
                message=f"Glass {panel.id} is SCRAP; process is blocked",
            )
        ]

    eq_product = EQUIPMENT_PRODUCT.get(equipment.id)
    if eq_product and eq_product != lot.product_type:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.PRODUCT_ROUTE_VIOLATION,
                message=(
                    f"{lot.product_type} lot {lot.id} cannot enter {equipment.id} "
                    f"(scope={eq_product})"
                ),
            )
        ]

    recipe_steps = {
        ProcessStep.CLEAN.value,
        ProcessStep.EVAP.value,
        ProcessStep.ENCAP.value,
        ProcessStep.PI.value,
        ProcessStep.LCD_CELL.value,
    }
    if expected_eq_step in recipe_steps:
        if not equipment.current_recipe_id:
            return [
                CheckResult(
                    reject=True,
                    code=AlarmCode.RECIPE_NOT_SELECTED,
                    message=f"{equipment.id} has no Recipe selected; host SELECT_RECIPE first",
                )
            ]
        if payload.recipe_id and payload.recipe_id != equipment.current_recipe_id:
            return [
                CheckResult(
                    reject=True,
                    code=AlarmCode.RECIPE_MISMATCH,
                    message=(
                        f"{equipment.id} PPID={equipment.current_recipe_id} "
                        f"but event recipe_id={payload.recipe_id}"
                    ),
                )
            ]

    if (
        equipment.equipment_status == EquipmentStatus.RUN.value
        and equipment.current_lot_id
        and equipment.current_lot_id != lot.id
    ):
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.EQUIPMENT_BUSY,
                message=f"{equipment.id} is RUN with {equipment.current_lot_id}",
            )
        ]

    last = _last_step(db, panel.id)
    allowed = allowed_next_steps(lot.product_type, last)
    if step not in allowed:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.STEP_SEQUENCE_VIOLATION,
                message=(
                    f"{lot.product_type} glass {panel.id} last_step={last} "
                    f"cannot jump to {step}; allowed={sorted(allowed)}"
                ),
            )
        ]

    if lot.status == LotStatus.HOLD.value:
        return [
            CheckResult(
                reject=True,
                code=AlarmCode.INTERLOCK_VIOLATION,
                message=f"LOT {lot.id} is HOLD ({lot.hold_reason}); OLED/LCD process advance blocked",
            )
        ]

    if payload.recipe_id and payload.recipe_id != lot.expected_recipe_id:
        reported = db.get(Recipe, payload.recipe_id)
        if reported and reported.product_type != lot.product_type:
            results.append(
                CheckResult(
                    reject=False,
                    code=AlarmCode.PRODUCT_ROUTE_VIOLATION,
                    message=(
                        f"Lot product {lot.product_type} but recipe {payload.recipe_id} "
                        f"is {reported.product_type}"
                    ),
                    severity=AlarmSeverity.CRITICAL,
                    hold_lot=True,
                )
            )
        results.append(
            CheckResult(
                reject=False,
                code=AlarmCode.RECIPE_MISMATCH,
                message=f"Expected {lot.expected_recipe_id} but received {payload.recipe_id}",
                severity=AlarmSeverity.CRITICAL,
                hold_lot=True,
            )
        )

    recipe = db.get(Recipe, lot.expected_recipe_id)
    if recipe and payload.chamber_temperature is not None:
        if (
            payload.chamber_temperature < recipe.expected_temperature_min
            or payload.chamber_temperature > recipe.expected_temperature_max
        ):
            results.append(
                CheckResult(
                    reject=False,
                    code=AlarmCode.TEMPERATURE_OUT_OF_RANGE,
                    message=(
                        f"chamber_temperature={payload.chamber_temperature} "
                        f"not in [{recipe.expected_temperature_min}, {recipe.expected_temperature_max}]"
                    ),
                    severity=_temperature_severity(payload.chamber_temperature, recipe),
                )
            )

    if recipe and payload.vacuum_pressure is not None:
        if (
            payload.vacuum_pressure < recipe.expected_pressure_min
            or payload.vacuum_pressure > recipe.expected_pressure_max
        ):
            results.append(
                CheckResult(
                    reject=False,
                    code=AlarmCode.PRESSURE_OUT_OF_RANGE,
                    message=(
                        f"vacuum_pressure={payload.vacuum_pressure} "
                        f"not in [{recipe.expected_pressure_min}, {recipe.expected_pressure_max}]"
                    ),
                    severity=_pressure_severity(payload.vacuum_pressure, recipe),
                )
            )

    return results
