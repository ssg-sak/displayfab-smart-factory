def test_mes_board_is_not_real_mes(client):
    res = client.get("/api/mes/board")
    assert res.status_code == 200
    body = res.json()
    assert "생산 화면" in body["note"]
    assert len(body["equipment"]) == 8
    assert "orders" in body
    assert "lots" in body
    assert "holds" in body
    assert "production" in body


def test_mes_board_after_oled_pass_marks_inspect_done(client):
    run = client.post("/api/lab/scenarios/demo_oled_pass/run").json()
    assert run["ok"] is True
    board = client.get("/api/mes/board").json()
    lot = next(row for row in board["lots"] if row["lot_id"] == run["lot_id"])
    inspect = next(step for step in lot["route"] if step["step"] == "INSPECT")
    assert inspect["state"] == "done"
    assert inspect["done"] == inspect["total"]
    assert any(order["id"] and order["lot_id"] == run["lot_id"] for order in board["orders"])


def test_mes_board_hold_after_oled_fail(client):
    run = client.post("/api/lab/scenarios/demo_oled_fail/run").json()
    assert run["lot_status"] == "HOLD"
    board = client.get("/api/mes/board").json()
    held = next(row for row in board["holds"] if row["lot_id"] == run["lot_id"])
    assert held["status"] == "HOLD"
    assert held["hold_reason"] == "INSPECT_FAIL"
    inspect = next(step for step in held["route"] if step["step"] == "INSPECT")
    assert inspect["state"] == "hold"
