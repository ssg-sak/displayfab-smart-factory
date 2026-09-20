"""학습용 마스터. Recipe 범위는 실제 OLED/LCD 제조사양이 아니다."""

from sqlalchemy.orm import Session

from app.enums import ConnectionStatus, EquipmentStatus, InterfaceType, LotStatus, PanelStatus, ProcessStep, ProductType
from app.models import Equipment, Lot, Panel, Recipe

RECIPES = [
    {
        "id": "RCP-OLED-A01",
        "name": "Lab OLED Evap/Encap Recipe A",
        "product_type": ProductType.OLED.value,
        "expected_temperature_min": 110.0,
        "expected_temperature_max": 130.0,
        "expected_pressure_min": 0.003,
        "expected_pressure_max": 0.008,
    },
    {
        "id": "RCP-OLED-B01",
        "name": "Lab OLED Evap/Encap Recipe B",
        "product_type": ProductType.OLED.value,
        "expected_temperature_min": 140.0,
        "expected_temperature_max": 160.0,
        "expected_pressure_min": 0.002,
        "expected_pressure_max": 0.006,
    },
    {
        "id": "RCP-LCD-C01",
        "name": "Lab LCD Cell Recipe C",
        "product_type": ProductType.LCD.value,
        "expected_temperature_min": 80.0,
        "expected_temperature_max": 95.0,
        "expected_pressure_min": 0.8,
        "expected_pressure_max": 1.2,
    },
]

EQUIPMENT = [
    {
        "id": "LOAD-01",
        "name": "Cassette Loader 01",
        "process_step": ProcessStep.LOAD.value,
        "product_scope": None,
    },
    {
        "id": "CLEAN-01",
        "name": "OLED Pre-Clean 01 (educational)",
        "process_step": ProcessStep.CLEAN.value,
        "product_scope": ProductType.OLED.value,
    },
    {
        "id": "PROC-01",
        "name": "OLED Evaporator 01 (educational)",
        "process_step": ProcessStep.EVAP.value,
        "product_scope": ProductType.OLED.value,
    },
    {
        "id": "PROC-02",
        "name": "OLED Evaporator 02 (educational)",
        "process_step": ProcessStep.EVAP.value,
        "product_scope": ProductType.OLED.value,
    },
    {
        "id": "ENC-01",
        "name": "OLED Encapsulator 01 (educational)",
        "process_step": ProcessStep.ENCAP.value,
        "product_scope": ProductType.OLED.value,
    },
    {
        "id": "PI-01",
        "name": "LCD PI Coat 01 (educational)",
        "process_step": ProcessStep.PI.value,
        "product_scope": ProductType.LCD.value,
    },
    {
        "id": "LCD-01",
        "name": "LCD Cell Process 01 (educational)",
        "process_step": ProcessStep.LCD_CELL.value,
        "product_scope": ProductType.LCD.value,
    },
    {
        "id": "INSPECT-01",
        "name": "Panel Inspection 01",
        "process_step": ProcessStep.INSPECT.value,
        "product_scope": None,
    },
]

LOTS = [
    {
        "id": "LOT-20260918-001",
        "cassette_id": "CST-OLED-001",
        "product_type": ProductType.OLED.value,
        "expected_recipe_id": "RCP-OLED-A01",
        "panels": [f"PNL-{i:05d}" for i in range(1, 6)],
    },
    {
        "id": "LOT-20260918-002",
        "cassette_id": "CST-OLED-002",
        "product_type": ProductType.OLED.value,
        "expected_recipe_id": "RCP-OLED-A01",
        "panels": [f"PNL-{i:05d}" for i in range(6, 11)],
    },
    {
        "id": "LOT-20260918-003",
        "cassette_id": "CST-LCD-003",
        "product_type": ProductType.LCD.value,
        "expected_recipe_id": "RCP-LCD-C01",
        "panels": [f"PNL-{i:05d}" for i in range(11, 16)],
    },
]


def ensure_masters(db: Session) -> None:
    for row in RECIPES:
        if db.get(Recipe, row["id"]) is None:
            db.add(Recipe(**row))
    for row in EQUIPMENT:
        eq = db.get(Equipment, row["id"])
        if eq is None:
            db.add(
                Equipment(
                    **row,
                    equipment_status=EquipmentStatus.IDLE.value,
                    connection_status=ConnectionStatus.OFFLINE.value,
                    interface_type=InterfaceType.SIMULATOR.value,
                    interface_endpoint="http://127.0.0.1:8000/api/events",
                )
            )
        else:
            if not eq.interface_type:
                eq.interface_type = InterfaceType.SIMULATOR.value
            if not eq.interface_endpoint:
                eq.interface_endpoint = "http://127.0.0.1:8000/api/events"
    db.commit()


def seed_if_empty(db: Session) -> None:
    empty = db.query(Equipment).first() is None
    ensure_masters(db)
    if not empty:
        return
    seed_sample_lots(db)


def seed_sample_lots(db: Session) -> None:
    """연습용 카세트 3개와 유리 15장. 초기화 후에도 이 상태로 돌아온다."""

    for lot_row in LOTS:
        db.add(
            Lot(
                id=lot_row["id"],
                cassette_id=lot_row["cassette_id"],
                product_type=lot_row["product_type"],
                expected_recipe_id=lot_row["expected_recipe_id"],
                status=LotStatus.WAIT.value,
            )
        )
        for slot, panel_id in enumerate(lot_row["panels"], start=1):
            db.add(
                Panel(
                    id=panel_id,
                    lot_id=lot_row["id"],
                    slot_no=slot,
                    status=PanelStatus.WAIT.value,
                )
            )

    db.commit()
