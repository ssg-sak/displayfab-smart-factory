"""OLED/LCD 축소 라우트와 인터록 규칙.

실제 Array/Cell/Module 전체 공정이 아니다.
디스플레이 제조 SW가 제품군·Cassette·Glass·설비를 어떻게 거르는지 연습한다.
"""

from app.enums import ProcessStep, ProductType

STEP_ALIASES = {
    ProcessStep.DEPOSITION.value: ProcessStep.EVAP.value,
    "DEPO": ProcessStep.EVAP.value,
    "CELL": ProcessStep.LCD_CELL.value,
    "PI_COAT": ProcessStep.PI.value,
}

OLED_ROUTE = [
    ProcessStep.LOAD.value,
    ProcessStep.CLEAN.value,
    ProcessStep.EVAP.value,
    ProcessStep.ENCAP.value,
    ProcessStep.INSPECT.value,
]

LCD_ROUTE = [
    ProcessStep.LOAD.value,
    ProcessStep.PI.value,
    ProcessStep.LCD_CELL.value,
    ProcessStep.INSPECT.value,
]

EQUIPMENT_STEP = {
    "LOAD-01": ProcessStep.LOAD.value,
    "CLEAN-01": ProcessStep.CLEAN.value,
    "PROC-01": ProcessStep.EVAP.value,
    "PROC-02": ProcessStep.EVAP.value,
    "ENC-01": ProcessStep.ENCAP.value,
    "PI-01": ProcessStep.PI.value,
    "LCD-01": ProcessStep.LCD_CELL.value,
    "INSPECT-01": ProcessStep.INSPECT.value,
}

EQUIPMENT_PRODUCT = {
    "LOAD-01": None,
    "CLEAN-01": ProductType.OLED.value,
    "PROC-01": ProductType.OLED.value,
    "PROC-02": ProductType.OLED.value,
    "ENC-01": ProductType.OLED.value,
    "PI-01": ProductType.LCD.value,
    "LCD-01": ProductType.LCD.value,
    "INSPECT-01": None,
}

OLED_EQUIPMENT = ["LOAD-01", "CLEAN-01", "PROC-01", "PROC-02", "ENC-01", "INSPECT-01"]
LCD_EQUIPMENT = ["LOAD-01", "PI-01", "LCD-01", "INSPECT-01"]

# 공정별 이론 사이클(초). 이 시스템이 정한 기준값이고 현장 스펙이 아니다.
# 시뮬레이터가 보고하는 cycle_time_sec와 OEE Performance의 분자가 같은 값을 쓴다.
IDEAL_CYCLE_SEC = {
    ProcessStep.LOAD.value: None,
    ProcessStep.CLEAN.value: 18.0,
    ProcessStep.EVAP.value: 46.0,
    ProcessStep.ENCAP.value: 30.0,
    ProcessStep.PI.value: 22.0,
    ProcessStep.LCD_CELL.value: 40.0,
    ProcessStep.INSPECT.value: 12.0,
}


def ideal_cycle_sec(step: str | None) -> float | None:
    if step is None:
        return None
    return IDEAL_CYCLE_SEC.get(normalize_step(step) or step)


def normalize_step(step: str | None) -> str | None:
    if step is None:
        return None
    return STEP_ALIASES.get(step, step)


def route_for(product_type: str) -> list[str]:
    if product_type == ProductType.LCD.value:
        return list(LCD_ROUTE)
    return list(OLED_ROUTE)


def equipment_ids_for_step(step: str | None) -> list[str]:
    if step is None:
        return []
    step = normalize_step(step) or step
    return [equipment_id for equipment_id, eq_step in EQUIPMENT_STEP.items() if eq_step == step]


def equipment_for_step(step: str | None) -> str | None:
    ids = equipment_ids_for_step(step)
    return ids[0] if ids else None


def next_operation(product_type: str, last_step: str | None) -> tuple[str | None, str | None]:
    """마지막 실적 다음으로 호스트가 보내는 공정. 끝나면 (None, None)."""
    route = route_for(product_type)
    last_step = normalize_step(last_step) if last_step else None
    if last_step is None or last_step not in route:
        step = route[0]
        return step, equipment_for_step(step)
    idx = route.index(last_step)
    if idx + 1 >= len(route):
        return None, None
    step = route[idx + 1]
    return step, equipment_for_step(step)


def allowed_next_steps(product_type: str, last_step: str | None) -> set[str]:
    route = route_for(product_type)
    if last_step is None:
        return {route[0]}
    last_step = normalize_step(last_step) or last_step
    if last_step not in route:
        return {route[0]}
    idx = route.index(last_step)
    allowed = {last_step}
    if idx + 1 < len(route):
        allowed.add(route[idx + 1])
    return allowed
