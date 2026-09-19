import uuid

from app.enums import CommandType, EquipmentStatus, EventType, LotStatus, ProcessStep
from app.models import Equipment, Lot
from app.schemas import CommandIn, EquipmentEventIn
from app.services.commands import execute_command
from app.services.collector import collect_push
from app.services.timeutil import utcnow

LINE_EQUIPMENT = [
    "LOAD-01",
    "CLEAN-01",
    "PROC-01",
    "PROC-02",
    "ENC-01",
    "PI-01",
    "LCD-01",
    "INSPECT-01",
]

RECIPE_EQUIPMENT = {
    "CLEAN-01": "OLED",
    "PROC-01": "OLED",
    "PROC-02": "OLED",
    "ENC-01": "OLED",
    "PI-01": "LCD",
    "LCD-01": "LCD",
}


def wake_equipment(db, equipment_id: str) -> None:
    collect_push(
        db,
        EquipmentEventIn(
            equipment_id=equipment_id,
            event_type=EventType.HEARTBEAT,
            equipment_status=EquipmentStatus.RUN,
            timestamp=utcnow(),
        ),
        str(uuid.uuid4()),
        str(uuid.uuid4()),
    )


def prepare_equipment(db, equipment_id: str, recipe_id: str | None = None) -> None:
    eq = db.get(Equipment, equipment_id)
    if eq is None:
        return
    if eq.equipment_status == EquipmentStatus.MAINTENANCE.value:
        return
    if eq.current_lot_id:
        occupying = db.get(Lot, eq.current_lot_id)
        if occupying is None or occupying.status != LotStatus.PROCESSING.value:
            eq.current_lot_id = None
    wake_equipment(db, equipment_id)
    if eq.equipment_status != EquipmentStatus.RUN.value:
        execute_command(db, CommandIn(command_type=CommandType.START, equipment_id=equipment_id))
    if recipe_id and equipment_id in RECIPE_EQUIPMENT:
        execute_command(
            db,
            CommandIn(command_type=CommandType.SELECT_RECIPE, equipment_id=equipment_id, recipe_id=recipe_id),
        )


def prepare_line(db, recipe_id: str) -> None:
    oled = recipe_id.startswith("RCP-OLED")
    for eq_id in LINE_EQUIPMENT:
        scope = RECIPE_EQUIPMENT.get(eq_id)
        rid = None
        if scope == "OLED" and oled:
            rid = recipe_id
        elif scope == "LCD" and not oled:
            rid = recipe_id
        elif scope == "OLED":
            rid = "RCP-OLED-A01"
        elif scope == "LCD":
            rid = "RCP-LCD-C01"
        prepare_equipment(db, eq_id, rid)


def recipe_step(step: str | None) -> bool:
    return step in {
        ProcessStep.CLEAN.value,
        ProcessStep.EVAP.value,
        ProcessStep.ENCAP.value,
        ProcessStep.PI.value,
        ProcessStep.LCD_CELL.value,
    }
