from datetime import datetime, timedelta, timezone

from app.enums import AlarmCode, ConnectionStatus, LotStatus
from app.models import Equipment
from app.services.offline import mark_offline_equipment
from tests.conftest import clean_glass, load_glass, make_event, select_recipe, utc_ts


def test_valid_process_event(client):
    load = load_glass(client)
    assert load.json()["accepted"] is True
    assert clean_glass(client).json()["accepted"] is True
    res = client.post("/api/events", json=make_event())
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is True
    assert body["lot_status"] == LotStatus.PROCESSING.value
    assert body["alarms"] == []


def test_unknown_equipment(client):
    res = client.post("/api/events", json=make_event(equipment_id="FAKE-99"))
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is False
    assert body["reason"] == AlarmCode.UNKNOWN_EQUIPMENT.value
    alarms = client.get("/api/alarms").json()
    assert any(a["alarm_code"] == AlarmCode.UNKNOWN_EQUIPMENT.value for a in alarms)


def test_unknown_lot(client):
    res = client.post("/api/events", json=make_event(lot_id="LOT-NOPE"))
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is False
    assert body["reason"] == AlarmCode.INVALID_LOT.value


def test_wrong_panel(client):
    res = client.post(
        "/api/events",
        json=make_event(lot_id="LOT-20260918-002", panel_id="PNL-00001"),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is False
    assert body["reason"] == AlarmCode.INVALID_PANEL.value


def test_recipe_mismatch(client):
    load_glass(client)
    clean_glass(client)
    select_recipe(client, "PROC-01", "RCP-OLED-B01")
    res = client.post("/api/events", json=make_event(recipe_id="RCP-OLED-B01"))
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is True
    assert any(a["alarm_code"] == AlarmCode.RECIPE_MISMATCH.value for a in body["alarms"])
    assert body["lot_status"] == LotStatus.HOLD.value


def test_temperature_alarm(client):
    load_glass(client)
    clean_glass(client)
    res = client.post("/api/events", json=make_event(chamber_temperature=210.0))
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is True
    assert any(a["alarm_code"] == AlarmCode.TEMPERATURE_OUT_OF_RANGE.value for a in body["alarms"])


def test_pressure_alarm(client):
    load_glass(client)
    clean_glass(client)
    res = client.post("/api/events", json=make_event(vacuum_pressure=0.9))
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is True
    assert any(a["alarm_code"] == AlarmCode.PRESSURE_OUT_OF_RANGE.value for a in body["alarms"])


def test_duplicate_event(client):
    load_glass(client)
    clean_glass(client)
    payload = make_event(timestamp=utc_ts(-1))
    first = client.post("/api/events", json=payload)
    second = client.post("/api/events", json=payload)
    assert first.json()["accepted"] is True
    assert second.json()["accepted"] is False
    assert second.json()["reason"] == AlarmCode.DUPLICATE_EVENT.value


def test_stale_event(client):
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    res = client.post("/api/events", json=make_event(timestamp=old))
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is False
    assert body["reason"] == AlarmCode.STALE_TIMESTAMP.value


def test_equipment_offline(client, db_session):
    res = client.post(
        "/api/events",
        json=make_event(event_type="HEARTBEAT", lot_id=None, panel_id=None, process_step=None, equipment_status="IDLE"),
    )
    assert res.json()["accepted"] is True

    db = db_session
    eq = db.get(Equipment, "PROC-01")
    eq.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=15)
    db.commit()
    changed = mark_offline_equipment(db)
    assert "PROC-01" in changed
    eq = db.get(Equipment, "PROC-01")
    assert eq.connection_status == ConnectionStatus.OFFLINE.value

    body = client.get("/api/equipment/PROC-01").json()
    assert body["connection_status"] == ConnectionStatus.OFFLINE.value
    alarms = client.get("/api/alarms").json()
    assert any(a["alarm_code"] == AlarmCode.COMMUNICATION_LOSS.value for a in alarms)

    process = client.post("/api/events", json=make_event())
    assert process.json()["accepted"] is False
    assert process.json()["reason"] == AlarmCode.COMMUNICATION_LOSS.value


def test_lot_hold(client):
    load_glass(client)
    clean_glass(client)
    select_recipe(client, "PROC-01", "RCP-OLED-B01")
    client.post("/api/events", json=make_event(recipe_id="RCP-OLED-B01"))
    lot = client.get("/api/lots/LOT-20260918-001").json()
    assert lot["status"] == LotStatus.HOLD.value
    assert lot["hold_reason"] == AlarmCode.RECIPE_MISMATCH.value
    assert lot["product_type"] == "OLED"
    assert lot["cassette_id"] == "CST-OLED-001"


def test_process_history(client):
    client.post("/api/events", json=make_event(equipment_id="LOAD-01", process_step="LOAD", timestamp=utc_ts(-5)))
    client.post("/api/events", json=make_event(equipment_id="CLEAN-01", process_step="CLEAN", timestamp=utc_ts(-4)))
    client.post("/api/events", json=make_event(timestamp=utc_ts(-3)))
    client.post(
        "/api/events",
        json=make_event(equipment_id="ENC-01", process_step="ENCAP", timestamp=utc_ts(-2)),
    )
    client.post(
        "/api/events",
        json=make_event(
            equipment_id="INSPECT-01",
            process_step="INSPECT",
            inspect_result="PASS",
            timestamp=utc_ts(-1),
        ),
    )
    history = client.get("/api/lots/LOT-20260918-001/history").json()
    assert len(history) == 5
    assert [h["equipment_id"] for h in history] == ["LOAD-01", "CLEAN-01", "PROC-01", "ENC-01", "INSPECT-01"]


def test_panel_traceability(client):
    client.post("/api/events", json=make_event(equipment_id="LOAD-01", process_step="LOAD", timestamp=utc_ts(-5)))
    client.post("/api/events", json=make_event(equipment_id="CLEAN-01", process_step="CLEAN", timestamp=utc_ts(-4)))
    client.post("/api/events", json=make_event(timestamp=utc_ts(-3)))
    client.post("/api/events", json=make_event(equipment_id="ENC-01", process_step="ENCAP", timestamp=utc_ts(-2)))
    client.post(
        "/api/events",
        json=make_event(
            equipment_id="INSPECT-01",
            process_step="INSPECT",
            inspect_result="PASS",
            timestamp=utc_ts(-1),
        ),
    )
    history = client.get("/api/panels/PNL-00001/history").json()
    assert [h["process_step"] for h in history] == ["LOAD", "CLEAN", "EVAP", "ENCAP", "INSPECT"]
    assert history[-1]["inspect_result"] == "PASS"
