from app.services.line_runner import run_work_order


def test_run_order_oled_five_steps(client):
    wo = client.post("/api/work-orders", json={"product_type": "OLED", "qty": 1}).json()
    res = client.post("/api/lab/run-order/" + wo["id"])
    body = res.json()
    assert res.status_code == 200
    assert body["ok"] is True
    assert body["status"] == "DONE"
    assert body["count"] == 5
    assert all(row["accepted"] for row in body["results"])
    steps = [row["process_step"] for row in body["results"]]
    assert steps == ["LOAD", "CLEAN", "EVAP", "ENCAP", "INSPECT"]
    today = client.get("/api/production").json()
    assert today["oled"]["complete"] == 1
    assert today["oled"]["target"] == 1
    order = client.get("/api/work-orders").json()[0]
    assert order["id"] == wo["id"]
    assert order["status"] == "DONE"


def test_run_order_lcd_four_steps(client):
    wo = client.post("/api/work-orders", json={"product_type": "LCD", "qty": 1}).json()
    res = client.post("/api/lab/run-order/" + wo["id"])
    body = res.json()
    assert res.status_code == 200
    assert body["ok"] is True
    assert body["status"] == "DONE"
    assert body["count"] == 4
    steps = [row["process_step"] for row in body["results"]]
    assert steps == ["LOAD", "PI", "LCD_CELL", "INSPECT"]
    today = client.get("/api/production").json()
    assert today["lcd"]["complete"] == 1
    assert today["lcd"]["target"] == 1


def test_run_order_missing_work_order(client):
    res = client.post("/api/lab/run-order/WO-NOPE")
    assert res.status_code == 404


def test_run_order_inspect_fail_holds(client, db_session):
    wo = client.post("/api/work-orders", json={"product_type": "OLED", "qty": 1}).json()
    result = run_work_order(db_session, wo["id"], inspect_result="FAIL")
    assert result["ok"] is False
    assert "HOLD" in result["error"]
    steps = [row["process_step"] for row in result["results"]]
    assert steps == ["LOAD", "CLEAN", "EVAP", "ENCAP", "INSPECT"]
    assert result["results"][-1]["accepted"] is True
    lot = client.get("/api/lots/" + wo["lot_id"]).json()
    assert lot["status"] == "HOLD"
