from datetime import datetime, timedelta, timezone

from app.adapters.opcua import OPCUAAdapter
from app.models import Equipment
from app.services.offline import mark_offline_equipment
from tests.conftest import load_glass, make_event, utc_ts


def test_equipment_interface_is_simulator(client):
    row = client.get("/api/equipment/PROC-01").json()
    assert row["interface_type"] == "simulator"
    assert row["interface_endpoint"].endswith("/api/events")
    iface = client.get("/api/equipment/PROC-01/interface").json()
    assert iface["adapter"] == "simulator"
    assert iface["transport"] == "HTTP/JSON"
    assert iface["poll_implemented"] is True


def test_heartbeat_writes_telemetry(client):
    res = client.post(
        "/api/events",
        json={
            "equipment_id": "PROC-01",
            "event_type": "HEARTBEAT",
            "equipment_status": "IDLE",
            "chamber_temperature": 118.0,
            "vacuum_pressure": 0.004,
            "timestamp": utc_ts(),
        },
    )
    assert res.json()["accepted"] is True
    rows = client.get("/api/equipment/PROC-01/telemetry").json()
    assert rows
    assert rows[0]["source"] == "HEARTBEAT"
    assert rows[0]["chamber_temperature"] == 118.0
    assert rows[0]["interface_type"] == "simulator"


def test_process_writes_telemetry_and_keeps_sensor_reading(client):
    load_glass(client)
    client.post(
        "/api/events",
        json=make_event(equipment_id="CLEAN-01", process_step="CLEAN", timestamp=utc_ts(-4)),
    )
    res = client.post("/api/events", json=make_event())
    assert res.json()["accepted"] is True
    tel = client.get("/api/equipment/PROC-01/telemetry").json()
    assert any(row["source"] == "PROCESS" for row in tel)
    history = client.get("/api/lots/LOT-20260918-001/history").json()
    evap = next(item for item in history if item["process_step"] == "EVAP")
    assert evap["chamber_temperature"] == 118.4


def test_command_goes_through_simulator_adapter(client):
    res = client.post("/api/commands", json={"command_type": "STOP", "equipment_id": "PROC-01"})
    body = res.json()
    assert body["status"] == "ACCEPTED"
    assert body["interface_type"] == "simulator"
    assert body["delivered_at"] is not None
    down = client.get("/api/equipment/PROC-01/downtime").json()
    assert any(row["reason"] == "STOP" and row["ended_at"] is None for row in down)
    client.post("/api/commands", json={"command_type": "START", "equipment_id": "PROC-01"})
    down = client.get("/api/equipment/PROC-01/downtime").json()
    stop = next(row for row in down if row["reason"] == "STOP")
    assert stop["ended_at"] is not None
    assert stop["duration_sec"] is not None


def test_offline_opens_and_heartbeat_closes_downtime(client, db_session):
    hb = client.post(
        "/api/events",
        json={
            "equipment_id": "PROC-01",
            "event_type": "HEARTBEAT",
            "equipment_status": "IDLE",
            "timestamp": utc_ts(),
        },
    )
    assert hb.json()["accepted"] is True
    db = db_session
    eq = db.get(Equipment, "PROC-01")
    eq.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=15)
    db.commit()
    changed = mark_offline_equipment(db)
    assert "PROC-01" in changed
    down = client.get("/api/equipment/PROC-01/downtime").json()
    assert any(row["reason"] == "COMMUNICATION_LOSS" and row["ended_at"] is None for row in down)
    client.post(
        "/api/events",
        json={
            "equipment_id": "PROC-01",
            "event_type": "HEARTBEAT",
            "equipment_status": "IDLE",
            "timestamp": utc_ts(),
        },
    )
    down = client.get("/api/equipment/PROC-01/downtime").json()
    loss = next(row for row in down if row["reason"] == "COMMUNICATION_LOSS")
    assert loss["ended_at"] is not None


def test_opcua_adapter_is_not_implemented():
    adapter = OPCUAAdapter()
    try:
        adapter.connect()
        raise AssertionError("OPC UA must stay unimplemented")
    except NotImplementedError:
        pass


def test_unknown_equipment_does_not_write_telemetry(client):
    client.post("/api/events", json=make_event(equipment_id="FAKE-99"))
    res = client.get("/api/equipment/FAKE-99/telemetry")
    assert res.status_code == 404
