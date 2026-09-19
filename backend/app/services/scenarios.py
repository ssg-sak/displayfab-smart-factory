from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.enums import CommandType, EquipmentStatus, EventType, PanelStatus
from app.models import Equipment, Lot, Panel
from app.schemas import CommandIn, EquipmentEventIn
from app.services.commands import execute_command
from app.services.collector import collect_push
from app.services.demo import run_demo
from app.services.host_prep import prepare_line
from app.services.offline import mark_offline_equipment
from app.services.timeutil import utcnow
from app.services.work_orders import create_and_release

CATALOG = [
    {
        "id": "demo_oled_pass",
        "title": "올레드 1장 투입",
        "what": "오늘 지시를 만들고 투입→세정→증착→봉지→검사 합격",
    },
    {
        "id": "demo_oled_fail",
        "title": "검사 불량",
        "what": "오늘 지시 1장이 검사에서 불량이 나와 보류됩니다",
    },
    {
        "id": "demo_lcd_pass",
        "title": "엘시디 1장",
        "what": "오늘 지시로 투입→배향막→셀 공정→검사 합격",
    },
    {
        "id": "demo_comm_loss",
        "title": "줄 끊기",
        "what": "증착 1호기 생존신호를 끊어 실적을 막습니다",
    },
    {
        "id": "demo_alive",
        "title": "다시 살리기",
        "what": "라인 설비에 생존신호를 다시 보냅니다",
    },
    {
        "id": "demo_recipe_mismatch",
        "title": "조건 틀림",
        "what": "오늘 지시 1장이 증착에서 조건이 달라 보류됩니다",
    },
    {
        "id": "oled_happy",
        "title": "OLED 정상 1장",
        "what": "연습용 카세트로 투입→세정→증착→봉지→검사 합격",
    },
    {
        "id": "lcd_happy",
        "title": "LCD 정상 1장",
        "what": "연습용 카세트로 투입→PI 도포→셀 공정→검사 합격",
    },
    {
        "id": "lcd_into_oled_evap",
        "title": "LCD 유리가 OLED 증착에 들어감",
        "what": "제품 경로 오류로 거절됩니다",
    },
    {
        "id": "oled_recipe_mismatch",
        "title": "OLED 조건이 다름",
        "what": "조건이 달라 작업이 보류됩니다",
    },
    {
        "id": "oled_skip_encap",
        "title": "OLED 봉지를 건너뜀",
        "what": "공정 순서가 달라 거절됩니다",
    },
    {
        "id": "oled_inspect_fail",
        "title": "OLED 검사 불량",
        "what": "검사 불량으로 보류됩니다. 폐기하거나 다시 검사합니다",
    },
    {
        "id": "heartbeat",
        "title": "증착 1호기 생존신호",
        "what": "작업 없이 설비가 살아 있다고만 알립니다",
    },
]


def _wait_panel(db: Session, lot_id: str) -> Panel | None:
    return (
        db.query(Panel)
        .filter(Panel.lot_id == lot_id, Panel.status == PanelStatus.WAIT.value)
        .order_by(Panel.slot_no.asc())
        .first()
    )


def _ingest(db: Session, payload: EquipmentEventIn) -> dict:
    event_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    accepted, reason, alarms, lot_status = collect_push(db, payload, request_id, event_id)
    return {
        "accepted": accepted,
        "reason": reason,
        "lot_status": lot_status,
        "event_id": event_id,
        "alarms": [a.alarm_code for a in alarms],
        "equipment_id": payload.equipment_id,
        "process_step": payload.process_step,
    }


def _ts(offset: int):
    return utcnow() + timedelta(seconds=offset)


def _process(**kwargs) -> EquipmentEventIn:
    body = {
        "event_type": EventType.PROCESS,
        "equipment_status": EquipmentStatus.RUN,
        "timestamp": utcnow(),
    }
    body.update(kwargs)
    return EquipmentEventIn(**body)


def _demo_recipe_mismatch(db: Session) -> dict:
    prepare_line(db, "RCP-OLED-A01")
    order, panel_ids = create_and_release(
        db,
        product_type="OLED",
        recipe_id="RCP-OLED-A01",
        qty=1,
    )
    panel_id = panel_ids[0]
    lot_id = order.lot_id
    results = []
    steps = [
        ("LOAD-01", "LOAD", None, "RCP-OLED-A01"),
        ("CLEAN-01", "CLEAN", 18.0, "RCP-OLED-A01"),
    ]
    for i, (eq, step, cycle, recipe) in enumerate(steps):
        results.append(
            _ingest(
                db,
                _process(
                    equipment_id=eq,
                    lot_id=lot_id,
                    panel_id=panel_id,
                    process_step=step,
                    recipe_id=recipe,
                    chamber_temperature=118.4,
                    vacuum_pressure=0.0041,
                    cycle_time_sec=cycle,
                    timestamp=_ts(i),
                ),
            )
        )
    execute_command(
        db,
        CommandIn(command_type=CommandType.SELECT_RECIPE, equipment_id="PROC-01", recipe_id="RCP-OLED-B01"),
    )
    results.append(
        _ingest(
            db,
            _process(
                equipment_id="PROC-01",
                lot_id=lot_id,
                panel_id=panel_id,
                process_step="EVAP",
                recipe_id="RCP-OLED-B01",
                chamber_temperature=148.0,
                vacuum_pressure=0.0035,
                cycle_time_sec=46.0,
                timestamp=_ts(2),
            ),
        )
    )
    lot = db.get(Lot, lot_id)
    return {
        "ok": True,
        "seed_used": False,
        "work_order_id": order.id,
        "lot_id": lot_id,
        "cassette_id": order.cassette_id,
        "panel_ids": panel_ids,
        "lot_status": lot.status if lot else None,
        "hold_reason": lot.hold_reason if lot else None,
        "results": results,
    }


def run_scenario(db: Session, scenario_id: str) -> dict:
    meta = next((row for row in CATALOG if row["id"] == scenario_id), None)
    if meta is None:
        return {"ok": False, "error": f"unknown scenario: {scenario_id}"}

    if scenario_id == "demo_oled_pass":
        return {**meta, **run_demo(db, product_type="OLED", recipe_id="RCP-OLED-A01", inspect_result="PASS")}
    if scenario_id == "demo_oled_fail":
        return {**meta, **run_demo(db, product_type="OLED", recipe_id="RCP-OLED-A01", inspect_result="FAIL")}
    if scenario_id == "demo_lcd_pass":
        return {**meta, **run_demo(db, product_type="LCD", recipe_id="RCP-LCD-C01", inspect_result="PASS")}
    if scenario_id == "demo_comm_loss":
        prepare_line(db, "RCP-OLED-A01")
        eq = db.get(Equipment, "PROC-01")
        if eq is None:
            return {"ok": False, **meta, "error": "증착 1호기가 없습니다"}
        eq.last_seen_at = utcnow() - timedelta(seconds=30)
        db.commit()
        changed = mark_offline_equipment(db)
        return {"ok": True, "seed_used": False, **meta, "offline": changed, "equipment_id": "PROC-01"}
    if scenario_id == "demo_alive":
        prepare_line(db, "RCP-OLED-A01")
        return {"ok": True, "seed_used": False, **meta}
    if scenario_id == "demo_recipe_mismatch":
        return {**meta, **_demo_recipe_mismatch(db)}

    results: list[dict] = []
    if scenario_id != "heartbeat":
        recipe = "RCP-LCD-C01" if scenario_id.startswith("lcd") else "RCP-OLED-A01"
        prepare_line(db, recipe)

    if scenario_id == "heartbeat":
        for eq_id in ["LOAD-01", "CLEAN-01", "PROC-01", "PROC-02", "ENC-01", "PI-01", "LCD-01", "INSPECT-01"]:
            results.append(
                _ingest(
                    db,
                    EquipmentEventIn(
                        equipment_id=eq_id,
                        event_type=EventType.HEARTBEAT,
                        equipment_status=EquipmentStatus.IDLE,
                        timestamp=_ts(0),
                    ),
                )
            )
        return {"ok": True, **meta, "results": results}

    if scenario_id == "oled_happy":
        panel = _wait_panel(db, "LOT-20260918-001")
        if panel is None:
            return {"ok": False, **meta, "error": "LOT-001에 WAIT Glass가 없다"}
        steps = [
            ("LOAD-01", "LOAD", None),
            ("CLEAN-01", "CLEAN", 18.0),
            ("PROC-01", "EVAP", 46.0),
            ("ENC-01", "ENCAP", 30.0),
            ("INSPECT-01", "INSPECT", 12.0),
        ]
        for i, (eq, step, cycle) in enumerate(steps):
            results.append(
                _ingest(
                    db,
                    _process(
                        equipment_id=eq,
                        lot_id=panel.lot_id,
                        panel_id=panel.id,
                        process_step=step,
                        recipe_id="RCP-OLED-A01",
                        chamber_temperature=118.4,
                        vacuum_pressure=0.0041,
                        cycle_time_sec=cycle,
                        inspect_result="PASS" if step == "INSPECT" else None,
                        timestamp=_ts(i),
                    ),
                )
            )
        return {"ok": True, **meta, "glass": panel.id, "results": results}

    if scenario_id == "lcd_happy":
        panel = _wait_panel(db, "LOT-20260918-003")
        if panel is None:
            return {"ok": False, **meta, "error": "LOT-003에 WAIT Glass가 없다"}
        steps = [
            ("LOAD-01", "LOAD", None),
            ("PI-01", "PI", 22.0),
            ("LCD-01", "LCD_CELL", 40.0),
            ("INSPECT-01", "INSPECT", 12.0),
        ]
        for i, (eq, step, cycle) in enumerate(steps):
            results.append(
                _ingest(
                    db,
                    _process(
                        equipment_id=eq,
                        lot_id=panel.lot_id,
                        panel_id=panel.id,
                        process_step=step,
                        recipe_id="RCP-LCD-C01",
                        chamber_temperature=88.0,
                        vacuum_pressure=1.0,
                        cycle_time_sec=cycle,
                        inspect_result="PASS" if step == "INSPECT" else None,
                        timestamp=_ts(i),
                    ),
                )
            )
        return {"ok": True, **meta, "glass": panel.id, "results": results}

    if scenario_id == "lcd_into_oled_evap":
        panel = _wait_panel(db, "LOT-20260918-003")
        if panel is None:
            return {"ok": False, **meta, "error": "LOT-003에 WAIT Glass가 없다"}
        results.append(
            _ingest(
                db,
                _process(
                    equipment_id="LOAD-01",
                    lot_id=panel.lot_id,
                    panel_id=panel.id,
                    process_step="LOAD",
                    recipe_id="RCP-LCD-C01",
                    chamber_temperature=88.0,
                    vacuum_pressure=1.0,
                    timestamp=_ts(0),
                ),
            )
        )
        results.append(
            _ingest(
                db,
                _process(
                    equipment_id="PROC-01",
                    lot_id=panel.lot_id,
                    panel_id=panel.id,
                    process_step="EVAP",
                    recipe_id="RCP-LCD-C01",
                    chamber_temperature=88.0,
                    vacuum_pressure=1.0,
                    timestamp=_ts(1),
                ),
            )
        )
        return {"ok": True, **meta, "glass": panel.id, "results": results}

    if scenario_id == "oled_recipe_mismatch":
        panel = _wait_panel(db, "LOT-20260918-002")
        if panel is None:
            return {"ok": False, **meta, "error": "LOT-002에 WAIT Glass가 없다"}
        results.append(
            _ingest(
                db,
                _process(
                    equipment_id="LOAD-01",
                    lot_id=panel.lot_id,
                    panel_id=panel.id,
                    process_step="LOAD",
                    recipe_id="RCP-OLED-A01",
                    chamber_temperature=118.4,
                    vacuum_pressure=0.0041,
                    timestamp=_ts(0),
                ),
            )
        )
        results.append(
            _ingest(
                db,
                _process(
                    equipment_id="CLEAN-01",
                    lot_id=panel.lot_id,
                    panel_id=panel.id,
                    process_step="CLEAN",
                    recipe_id="RCP-OLED-A01",
                    chamber_temperature=118.4,
                    vacuum_pressure=0.0041,
                    timestamp=_ts(1),
                ),
            )
        )
        execute_command(
            db,
            CommandIn(command_type=CommandType.SELECT_RECIPE, equipment_id="PROC-01", recipe_id="RCP-OLED-B01"),
        )
        results.append(
            _ingest(
                db,
                _process(
                    equipment_id="PROC-01",
                    lot_id=panel.lot_id,
                    panel_id=panel.id,
                    process_step="EVAP",
                    recipe_id="RCP-OLED-B01",
                    chamber_temperature=118.4,
                    vacuum_pressure=0.0041,
                    timestamp=_ts(2),
                ),
            )
        )
        return {"ok": True, **meta, "glass": panel.id, "results": results}

    if scenario_id == "oled_skip_encap":
        panel = _wait_panel(db, "LOT-20260918-001")
        if panel is None:
            return {"ok": False, **meta, "error": "LOT-001에 WAIT Glass가 없다"}
        results.append(
            _ingest(
                db,
                _process(
                    equipment_id="LOAD-01",
                    lot_id=panel.lot_id,
                    panel_id=panel.id,
                    process_step="LOAD",
                    recipe_id="RCP-OLED-A01",
                    chamber_temperature=118.4,
                    vacuum_pressure=0.0041,
                    timestamp=_ts(0),
                ),
            )
        )
        results.append(
            _ingest(
                db,
                _process(
                    equipment_id="CLEAN-01",
                    lot_id=panel.lot_id,
                    panel_id=panel.id,
                    process_step="CLEAN",
                    recipe_id="RCP-OLED-A01",
                    chamber_temperature=118.4,
                    vacuum_pressure=0.0041,
                    timestamp=_ts(1),
                ),
            )
        )
        results.append(
            _ingest(
                db,
                _process(
                    equipment_id="PROC-01",
                    lot_id=panel.lot_id,
                    panel_id=panel.id,
                    process_step="EVAP",
                    recipe_id="RCP-OLED-A01",
                    chamber_temperature=118.4,
                    vacuum_pressure=0.0041,
                    timestamp=_ts(2),
                ),
            )
        )
        results.append(
            _ingest(
                db,
                _process(
                    equipment_id="INSPECT-01",
                    lot_id=panel.lot_id,
                    panel_id=panel.id,
                    process_step="INSPECT",
                    recipe_id="RCP-OLED-A01",
                    inspect_result="PASS",
                    chamber_temperature=118.4,
                    vacuum_pressure=0.0041,
                    timestamp=_ts(3),
                ),
            )
        )
        return {"ok": True, **meta, "glass": panel.id, "results": results}

    if scenario_id == "oled_inspect_fail":
        panel = _wait_panel(db, "LOT-20260918-001")
        if panel is None:
            return {"ok": False, **meta, "error": "LOT-001에 WAIT Glass가 없다"}
        steps = [
            ("LOAD-01", "LOAD", None, None),
            ("CLEAN-01", "CLEAN", 18.0, None),
            ("PROC-01", "EVAP", 46.0, None),
            ("ENC-01", "ENCAP", 30.0, None),
            ("INSPECT-01", "INSPECT", 12.0, "FAIL"),
        ]
        for i, (eq, step, cycle, inspect) in enumerate(steps):
            results.append(
                _ingest(
                    db,
                    _process(
                        equipment_id=eq,
                        lot_id=panel.lot_id,
                        panel_id=panel.id,
                        process_step=step,
                        recipe_id="RCP-OLED-A01",
                        chamber_temperature=118.4,
                        vacuum_pressure=0.0041,
                        cycle_time_sec=cycle,
                        inspect_result=inspect,
                        timestamp=_ts(i),
                    ),
                )
            )
        return {"ok": True, **meta, "glass": panel.id, "results": results}

    return {"ok": False, "error": "not implemented"}
