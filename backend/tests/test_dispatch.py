from tests.conftest import clean_glass, load_glass, make_event, utc_ts


def test_oled_dispatch_starts_at_load(client):
    body = client.get("/api/panels/PNL-00001/dispatch").json()
    assert body["next_step"] == "LOAD"
    assert body["next_equipment_id"] == "LOAD-01"
    assert body["done"] is False


def test_oled_dispatch_after_load_is_clean(client):
    res = load_glass(client)
    assert res.json()["next_step"] == "CLEAN"
    assert res.json()["next_equipment_id"] == "CLEAN-01"
    body = client.get("/api/panels/PNL-00001/dispatch").json()
    assert body["last_step"] == "LOAD"
    assert body["next_step"] == "CLEAN"
    assert body["next_equipment_id"] == "CLEAN-01"


def test_lcd_dispatch_after_load_is_pi(client):
    load_glass(client, lot_id="LOT-20260918-003", panel_id="PNL-00011", recipe_id="RCP-LCD-C01")
    body = client.get("/api/panels/PNL-00011/dispatch").json()
    assert body["next_step"] == "PI"
    assert body["next_equipment_id"] == "PI-01"


def test_wip_moves_after_load(client):
    before = client.get("/api/wip").json()
    load = before["by_step"]["LOAD"]
    clean = before["by_step"]["CLEAN"]
    load_glass(client)
    after = client.get("/api/wip").json()
    assert after["by_step"]["LOAD"] == load - 1
    assert after["by_step"]["CLEAN"] == clean + 1


def test_oled_happy_then_dispatch_done(client):
    run = client.post("/api/lab/scenarios/oled_happy/run").json()
    glass = run["glass"]
    body = client.get("/api/panels/" + glass + "/dispatch").json()
    assert body["done"] is True
    assert body["next_step"] is None
    lot = client.get("/api/lots/" + body["lot_id"] + "/dispatch").json()
    assert lot["done"] is False
    assert lot["next_step"] == "LOAD"


def test_wrong_next_step_still_rejected(client):
    load_glass(client)
    res = client.post(
        "/api/events",
        json=make_event(equipment_id="ENC-01", process_step="ENCAP", timestamp=utc_ts()),
    )
    assert res.json()["accepted"] is False


def test_evap_goes_to_proc02_when_proc01_maint(client):
    client.post("/api/commands", json={"command_type": "MAINT_ENTER", "equipment_id": "PROC-01"})
    load_glass(client)
    clean_glass(client)
    body = client.get("/api/panels/PNL-00001/dispatch").json()
    assert body["next_step"] == "EVAP"
    assert body["next_equipment_id"] == "PROC-02"
