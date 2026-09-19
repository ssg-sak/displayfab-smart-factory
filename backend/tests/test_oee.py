from datetime import timedelta

from app.config import settings
from app.models import EquipmentDowntime
from tests.conftest import clean_glass, load_glass, make_event, utc_ts


def _run_oled_glass(client, lot_id, panel_id, inspect="PASS"):
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


def test_oee_says_line_never_opened_when_nothing_reported(client):
    body = client.get("/api/analytics/oee").json()
    assert body["planned_sec"] == 0.0
    assert body["planned_basis"] == "라인이 오늘 열리지 않았다"
    assert body["availability"] is None
    assert body["oee"] is None
    assert "오늘 설비 보고가 없어 계획가동시간이 없다" in body["missing"]
    assert "현장 스펙이 아니다" in body["note"]


def test_oee_planned_time_starts_at_first_report(client):
    _run_oled_glass(client, "LOT-20260918-001", "PNL-00001")
    body = client.get("/api/analytics/oee").json()
    assert body["planned_basis"].startswith("오늘 첫 보고")
    # 첫 보고가 10초 전이므로 계획시간이 하루가 아니라 그 창이다
    assert 5 <= body["planned_sec"] <= 120


def test_oee_becomes_computable_after_production(client):
    res = _run_oled_glass(client, "LOT-20260918-001", "PNL-00001")
    assert res.json()["accepted"] is True
    body = client.get("/api/analytics/oee").json()
    assert body["quality"] == 1.0
    assert body["performance"] is not None
    assert body["oee"] is not None
    assert body["missing"] == []
    assert body["good"] == 1


def test_oee_quality_drops_on_inspect_fail(client):
    _run_oled_glass(client, "LOT-20260918-001", "PNL-00001", inspect="FAIL")
    body = client.get("/api/analytics/oee").json()
    assert body["bad"] == 1
    assert body["quality"] == 0.0
    assert body["oee"] == 0.0


def test_oee_availability_drops_with_downtime(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "oee_planned_minutes", 10)
    before = client.get("/api/analytics/oee").json()
    assert before["availability"] == 1.0

    client.post("/api/commands", json={"command_type": "STOP", "equipment_id": "PROC-01"})
    row = (
        db_session.query(EquipmentDowntime)
        .filter(EquipmentDowntime.equipment_id == "PROC-01")
        .one()
    )
    row.started_at = row.started_at - timedelta(minutes=5)
    db_session.commit()

    after = client.get("/api/analytics/oee").json()
    assert after["availability"] < 1.0
    proc = next(r for r in after["equipment"] if r["equipment_id"] == "PROC-01")
    assert proc["downtime_sec"] >= 300
    assert proc["availability"] is not None and proc["availability"] < 0.6


def test_equipment_oee_row_uses_ideal_cycle(client):
    _run_oled_glass(client, "LOT-20260918-001", "PNL-00001")
    rows = client.get("/api/analytics/oee").json()["equipment"]
    evap = next(row for row in rows if row["equipment_id"] == "PROC-01")
    assert evap["processed"] == 1
    assert evap["ideal_runtime_sec"] == 46.0
    load = next(row for row in rows if row["equipment_id"] == "LOAD-01")
    assert load["ideal_runtime_sec"] == 0.0


def test_interfaces_summary_for_ops_console(client):
    client.post(
        "/api/events",
        json={
            "equipment_id": "PROC-01",
            "event_type": "HEARTBEAT",
            "equipment_status": "IDLE",
            "chamber_temperature": 120.0,
            "vacuum_pressure": 0.005,
            "timestamp": utc_ts(),
        },
    )
    client.post("/api/commands", json={"command_type": "STOP", "equipment_id": "ENC-01"})
    rows = client.get("/api/equipment/interfaces").json()
    assert len(rows) == 8
    proc = next(row for row in rows if row["equipment_id"] == "PROC-01")
    assert proc["interface_type"] == "simulator"
    assert proc["transport"] == "HTTP/JSON"
    assert proc["chamber_temperature"] == 120.0
    assert proc["telemetry_count"] >= 1
    enc = next(row for row in rows if row["equipment_id"] == "ENC-01")
    assert enc["open_downtime_reason"] == "STOP"
