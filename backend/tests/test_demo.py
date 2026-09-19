def test_demo_oled_pass_uses_new_lot(client):
    before = client.get("/api/production").json()
    res = client.post("/api/lab/scenarios/demo_oled_pass/run")
    body = res.json()
    assert body["ok"] is True
    assert body["seed_used"] is False
    assert body["lot_id"] != "LOT-20260918-001"
    assert body["lot_status"] != "HOLD"
    today = client.get("/api/production").json()
    assert today["oled"]["complete"] == before["oled"]["complete"] + 1
    assert today["closeout"]["complete"] == before["closeout"]["complete"] + 1
    traveler = client.get("/api/lots/" + body["lot_id"] + "/traveler").json()
    assert traveler["slots"][0]["last_step"] == "INSPECT"
    assert traveler["slots"][0]["status"] == "COMPLETE"


def test_demo_oled_fail_holds(client):
    res = client.post("/api/lab/scenarios/demo_oled_fail/run")
    body = res.json()
    assert body["ok"] is True
    assert body["seed_used"] is False
    assert body["lot_status"] == "HOLD"
    assert body["hold_reason"] == "INSPECT_FAIL"
    diag = client.get("/api/lots/" + body["lot_id"] + "/diagnosis").json()
    assert "HOLD" in diag["summary"]
    assert diag["action"]


def test_demo_lcd_pass(client):
    res = client.post("/api/lab/scenarios/demo_lcd_pass/run")
    body = res.json()
    assert body["ok"] is True
    assert body["lot_id"].startswith("LOT-")
    traveler = client.get("/api/lots/" + body["lot_id"] + "/traveler").json()
    assert traveler["slots"][0]["last_step"] == "INSPECT"
    today = client.get("/api/production").json()
    assert today["lcd"]["complete"] >= 1


def test_demo_comm_loss_then_alive(client):
    lost = client.post("/api/lab/scenarios/demo_comm_loss/run").json()
    assert lost["ok"] is True
    eq = next(row for row in client.get("/api/equipment").json() if row["id"] == "PROC-01")
    assert eq["connection_status"] == "OFFLINE"
    board = client.get("/api/mes/board").json()
    assert board["equipment_offline"] >= 1
    alive = client.post("/api/lab/scenarios/demo_alive/run").json()
    assert alive["ok"] is True
    eq = next(row for row in client.get("/api/equipment").json() if row["id"] == "PROC-01")
    assert eq["connection_status"] == "ONLINE"


def test_demo_recipe_mismatch_holds(client):
    res = client.post("/api/lab/scenarios/demo_recipe_mismatch/run")
    body = res.json()
    assert body["ok"] is True
    assert body["lot_status"] == "HOLD"
    assert body["hold_reason"] == "RECIPE_MISMATCH"
