from tests.conftest import clean_glass, load_glass, make_event, utc_ts


def _oled_to_inspect(client, lot_id, panel_id, inspect="PASS"):
    load_glass(client, lot_id=lot_id, panel_id=panel_id, offset=-10)
    clean_glass(client, lot_id=lot_id, panel_id=panel_id, offset=-8)
    client.post(
        "/api/events",
        json=make_event(lot_id=lot_id, panel_id=panel_id, process_step="EVAP", equipment_id="PROC-01", timestamp=utc_ts(-6)),
    )
    client.post(
        "/api/events",
        json=make_event(lot_id=lot_id, panel_id=panel_id, process_step="ENCAP", equipment_id="ENC-01", timestamp=utc_ts(-4)),
    )
    return client.post(
        "/api/events",
        json=make_event(
            lot_id=lot_id,
            panel_id=panel_id,
            process_step="INSPECT",
            equipment_id="INSPECT-01",
            inspect_result=inspect,
            timestamp=utc_ts(-2),
        ),
    )


def test_production_target_from_work_order(client):
    before = client.get("/api/production").json()
    assert before["oled"]["target"] == 0
    wo = client.post("/api/work-orders", json={"product_type": "OLED", "qty": 2}).json()
    today = client.get("/api/production").json()
    assert today["oled"]["target"] == 2
    assert today["oled"]["complete"] == 0
    assert "올레드 완료 0 / 목표 2" in today["summary"]
    assert wo["complete"] == 0


def test_production_complete_and_work_order_done(client):
    wo = client.post("/api/work-orders", json={"product_type": "OLED", "qty": 1}).json()
    glass = wo["panel_ids"][0]
    res = _oled_to_inspect(client, wo["lot_id"], glass)
    assert res.json()["accepted"] is True
    today = client.get("/api/production").json()
    assert today["oled"]["target"] == 1
    assert today["oled"]["complete"] == 1
    order = client.get("/api/work-orders").json()[0]
    assert order["id"] == wo["id"]
    assert order["complete"] == 1
    assert order["status"] == "DONE"


def test_blocked_line_shows_hold(client):
    client.post("/api/lab/scenarios/oled_inspect_fail/run")
    today = client.get("/api/production").json()
    assert today["hold_lots"]
    assert "보류" in today["blocked"]


def test_closeout_counts_today_work_order(client):
    before = client.get("/api/production").json()["closeout"]
    client.post("/api/work-orders", json={"product_type": "OLED", "qty": 3})
    close = client.get("/api/production").json()["closeout"]
    assert close["target"] == before["target"] + 3
    assert close["remaining"] == before["remaining"] + 3
    assert "완료" in close["line"]
