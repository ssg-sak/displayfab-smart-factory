from app.enums import AlarmCode, LotStatus, PanelStatus
from tests.conftest import make_event, utc_ts


def test_inspect_fail_holds_lot(client):
    run = client.post("/api/lab/scenarios/oled_inspect_fail/run").json()
    assert run["ok"] is True
    glass = run["glass"]
    last = run["results"][-1]
    assert last["accepted"] is True
    assert AlarmCode.INSPECT_FAIL.value in last["alarms"]
    panel = client.get("/api/panels/" + glass + "/dispatch").json()
    assert panel["panel_status"] == PanelStatus.FAIL.value
    assert panel["next_step"] == "INSPECT"
    lot = client.get("/api/lots/" + panel["lot_id"]).json()
    assert lot["status"] == LotStatus.HOLD.value
    assert lot["hold_reason"] == AlarmCode.INSPECT_FAIL.value
    kpi = client.get("/api/kpis").json()
    assert kpi["inspect_fail"] >= 1
    wip = client.get("/api/wip").json()
    assert wip["fail"] >= 1


def test_scrap_blocks_process(client):
    run = client.post("/api/lab/scenarios/oled_inspect_fail/run").json()
    glass = run["glass"]
    lot_id = client.get("/api/panels/" + glass + "/dispatch").json()["lot_id"]
    scrap = client.post("/api/commands", json={"command_type": "SCRAP_PANEL", "panel_id": glass})
    assert scrap.json()["status"] == "ACCEPTED"
    client.post("/api/commands", json={"command_type": "RELEASE_LOT", "lot_id": lot_id})
    res = client.post(
        "/api/events",
        json=make_event(
            equipment_id="INSPECT-01",
            process_step="INSPECT",
            panel_id=glass,
            lot_id=lot_id,
            inspect_result="PASS",
            timestamp=utc_ts(),
        ),
    )
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == AlarmCode.PANEL_SCRAPPED.value
    panel = client.get("/api/panels/" + glass + "/dispatch").json()
    assert panel["panel_status"] == PanelStatus.SCRAP.value
    assert panel["done"] is True


def test_release_allows_reinspect(client):
    run = client.post("/api/lab/scenarios/oled_inspect_fail/run").json()
    glass = run["glass"]
    lot_id = client.get("/api/panels/" + glass + "/dispatch").json()["lot_id"]
    client.post("/api/commands", json={"command_type": "RELEASE_LOT", "lot_id": lot_id})
    res = client.post(
        "/api/events",
        json=make_event(
            equipment_id="INSPECT-01",
            process_step="INSPECT",
            panel_id=glass,
            lot_id=lot_id,
            inspect_result="PASS",
            timestamp=utc_ts(),
        ),
    )
    assert res.json()["accepted"] is True
    panel = client.get("/api/panels/" + glass + "/dispatch").json()
    assert panel["panel_status"] == PanelStatus.COMPLETE.value
    kpi = client.get("/api/kpis").json()
    assert kpi["inspect_pass"] >= 1
