from app.enums import AlarmCode, LotStatus
from tests.conftest import clean_glass, load_glass, make_event, select_recipe, utc_ts


def test_heartbeat_without_lot(client):
    res = client.post(
        "/api/events",
        json=make_event(event_type="HEARTBEAT", lot_id=None, panel_id=None, process_step=None, equipment_status="IDLE"),
    )
    assert res.json()["accepted"] is True
    eq = client.get("/api/equipment/PROC-01").json()
    assert eq["connection_status"] == "ONLINE"


def test_oled_skip_encap_rejected(client):
    load_glass(client)
    clean_glass(client)
    client.post("/api/events", json=make_event(timestamp=utc_ts(-2)))
    res = client.post(
        "/api/events",
        json=make_event(equipment_id="INSPECT-01", process_step="INSPECT", inspect_result="PASS"),
    )
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == AlarmCode.STEP_SEQUENCE_VIOLATION.value


def test_lcd_cannot_enter_oled_evap(client):
    load_glass(client, lot_id="LOT-20260918-003", panel_id="PNL-00011", recipe_id="RCP-LCD-C01")
    res = client.post(
        "/api/events",
        json=make_event(
            lot_id="LOT-20260918-003",
            panel_id="PNL-00011",
            recipe_id="RCP-LCD-C01",
            chamber_temperature=88.0,
            vacuum_pressure=1.0,
        ),
    )
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == AlarmCode.PRODUCT_ROUTE_VIOLATION.value


def test_lcd_cell_route(client):
    load_glass(client, lot_id="LOT-20260918-003", panel_id="PNL-00011", recipe_id="RCP-LCD-C01")
    pi_res = client.post(
        "/api/events",
        json=make_event(
            equipment_id="PI-01",
            process_step="PI",
            lot_id="LOT-20260918-003",
            panel_id="PNL-00011",
            recipe_id="RCP-LCD-C01",
            chamber_temperature=88.0,
            vacuum_pressure=1.0,
        ),
    )
    assert pi_res.json()["accepted"] is True
    res = client.post(
        "/api/events",
        json=make_event(
            equipment_id="LCD-01",
            process_step="LCD_CELL",
            lot_id="LOT-20260918-003",
            panel_id="PNL-00011",
            recipe_id="RCP-LCD-C01",
            chamber_temperature=88.0,
            vacuum_pressure=1.0,
        ),
    )
    assert res.json()["accepted"] is True
    lot = client.get("/api/lots/LOT-20260918-003").json()
    assert lot["product_type"] == "LCD"
    assert lot["current_step"] == "LCD_CELL"


def test_hold_blocks_next_step(client):
    load_glass(client)
    clean_glass(client)
    select_recipe(client, "PROC-01", "RCP-OLED-B01")
    client.post("/api/events", json=make_event(recipe_id="RCP-OLED-B01", timestamp=utc_ts(-2)))
    res = client.post(
        "/api/events",
        json=make_event(equipment_id="ENC-01", process_step="ENCAP"),
    )
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == AlarmCode.INTERLOCK_VIOLATION.value


def test_release_lot_command(client):
    load_glass(client)
    clean_glass(client)
    select_recipe(client, "PROC-01", "RCP-OLED-B01")
    client.post("/api/events", json=make_event(recipe_id="RCP-OLED-B01"))
    cmd = client.post("/api/commands", json={"command_type": "RELEASE_LOT", "lot_id": "LOT-20260918-001"})
    assert cmd.json()["status"] == "ACCEPTED"
    lot = client.get("/api/lots/LOT-20260918-001").json()
    assert lot["status"] == LotStatus.PROCESSING.value
    assert lot["hold_reason"] is None


def test_maintenance_blocks_process(client):
    client.post("/api/commands", json={"command_type": "MAINT_ENTER", "equipment_id": "PROC-01"})
    load_glass(client)
    clean_glass(client)
    res = client.post("/api/events", json=make_event())
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == AlarmCode.EQUIPMENT_MAINTENANCE.value


def test_diagnosis_for_hold(client):
    load_glass(client)
    clean_glass(client)
    select_recipe(client, "PROC-01", "RCP-OLED-B01")
    client.post("/api/events", json=make_event(recipe_id="RCP-OLED-B01"))
    diag = client.get("/api/lots/LOT-20260918-001/diagnosis").json()
    assert diag["status"] == "HOLD"
    assert diag["product_type"] == "OLED"
    assert diag["route"] == ["LOAD", "CLEAN", "EVAP", "ENCAP", "INSPECT"]
    assert diag["hold_reason"] == AlarmCode.RECIPE_MISMATCH.value
    assert diag["open_alarms"]
    assert "HOLD" in diag["summary"]
    assert diag["action"]
