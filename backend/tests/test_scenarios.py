from app.enums import AlarmCode


def test_list_scenarios(client):
    rows = client.get("/api/lab/scenarios").json()
    ids = {row["id"] for row in rows}
    assert "oled_happy" in ids
    assert "lcd_into_oled_evap" in ids
    assert "demo_oled_pass" in ids
    assert "demo_oled_fail" in ids
    assert "demo_comm_loss" in ids
    titles = {row["id"]: row["title"] for row in rows}
    assert "올레드 1장" in titles["demo_oled_pass"]


def test_oled_happy_scenario(client):
    res = client.post("/api/lab/scenarios/oled_happy/run")
    body = res.json()
    assert body["ok"] is True
    assert all(step["accepted"] for step in body["results"])
    history = client.get("/api/panels/" + body["glass"] + "/history").json()
    assert [h["process_step"] for h in history] == ["LOAD", "CLEAN", "EVAP", "ENCAP", "INSPECT"]


def test_lcd_into_oled_evap_scenario(client):
    res = client.post("/api/lab/scenarios/lcd_into_oled_evap/run")
    body = res.json()
    assert body["ok"] is True
    last = body["results"][-1]
    assert last["accepted"] is False
    assert last["reason"] == AlarmCode.PRODUCT_ROUTE_VIOLATION.value
