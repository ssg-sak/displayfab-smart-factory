from app.enums import AlarmCode, EquipmentStatus
from tests.conftest import clean_glass, load_glass, make_event


def test_process_without_start_rejected(client):
    client.post("/api/commands", json={"command_type": "STOP", "equipment_id": "LOAD-01"})
    res = load_glass(client)
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == AlarmCode.EQUIPMENT_STOPPED.value


def test_recipe_not_selected(client, db_session):
    from app.models import Equipment

    eq = db_session.get(Equipment, "CLEAN-01")
    eq.current_recipe_id = None
    db_session.commit()
    load_glass(client)
    res = clean_glass(client)
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == AlarmCode.RECIPE_NOT_SELECTED.value


def test_select_recipe_sets_ppid(client):
    res = client.post(
        "/api/commands",
        json={"command_type": "SELECT_RECIPE", "equipment_id": "PROC-02", "recipe_id": "RCP-OLED-B01"},
    )
    assert res.json()["status"] == "ACCEPTED"
    eq = client.get("/api/equipment/PROC-02").json()
    assert eq["current_recipe_id"] == "RCP-OLED-B01"
    assert eq["equipment_status"] == EquipmentStatus.RUN.value


def test_slot_map(client):
    body = client.get("/api/lots/LOT-20260918-001/slots").json()
    assert body["cassette_id"] == "CST-OLED-001"
    assert len(body["slots"]) == 5
    assert body["slots"][0]["slot_no"] == 1
    assert body["slots"][0]["panel_id"] == "PNL-00001"


def test_traveler_empty_then_after_load(client):
    empty = client.get("/api/lots/LOT-20260918-001/traveler").json()
    assert empty["slots"][0]["last_step"] is None
    load_glass(client)
    body = client.get("/api/lots/LOT-20260918-001/traveler").json()
    assert body["slots"][0]["last_step"] == "LOAD"
    assert body["slots"][0]["last_equipment_id"] == "LOAD-01"


def test_yield_by_equipment_after_happy(client):
    client.post("/api/lab/scenarios/oled_happy/run")
    kpi = client.get("/api/kpis").json()
    assert kpi["inspect_pass"] >= 1
    ids = [row["equipment_id"] for row in kpi["yield_by_equipment"]]
    assert "ENC-01" in ids


def test_ppid_event_mismatch_rejected(client):
    load_glass(client)
    clean_glass(client)
    res = client.post("/api/events", json=make_event(recipe_id="RCP-OLED-B01"))
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == AlarmCode.RECIPE_MISMATCH.value
    lot = client.get("/api/lots/LOT-20260918-001").json()
    assert lot["status"] != "HOLD"
