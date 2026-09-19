from app.enums import AlarmCode
from tests.conftest import clean_glass, load_glass, make_event, utc_ts


def test_create_oled_work_order(client):
    res = client.post(
        "/api/work-orders",
        json={"product_type": "OLED", "recipe_id": "RCP-OLED-A01", "qty": 3},
    )
    body = res.json()
    assert res.status_code == 200
    assert body["status"] == "RELEASED"
    assert body["qty"] == 3
    assert len(body["panel_ids"]) == 3
    lot = client.get("/api/lots/" + body["lot_id"]).json()
    assert lot["status"] == "WAIT"
    assert lot["product_type"] == "OLED"
    assert lot["cassette_id"] == body["cassette_id"]
    assert lot["panel_count"] == 3


def test_create_lcd_work_order(client):
    res = client.post("/api/work-orders", json={"product_type": "LCD", "qty": 2})
    body = res.json()
    assert res.status_code == 200
    assert body["recipe_id"] == "RCP-LCD-C01"
    assert body["product_type"] == "LCD"
    lot = client.get("/api/lots/" + body["lot_id"]).json()
    assert lot["product_type"] == "LCD"


def test_recipe_product_mismatch_rejected(client):
    res = client.post(
        "/api/work-orders",
        json={"product_type": "OLED", "recipe_id": "RCP-LCD-C01", "qty": 1},
    )
    assert res.status_code == 400


def test_stop_blocks_process(client):
    client.post("/api/commands", json={"command_type": "STOP", "equipment_id": "PROC-01"})
    load_glass(client)
    clean_glass(client)
    res = client.post("/api/events", json=make_event(timestamp=utc_ts()))
    body = res.json()
    assert body["accepted"] is False
    assert body["reason"] == AlarmCode.EQUIPMENT_STOPPED.value
    client.post("/api/commands", json={"command_type": "START", "equipment_id": "PROC-01"})
    res = client.post("/api/events", json=make_event(timestamp=utc_ts()))
    assert res.json()["accepted"] is True
