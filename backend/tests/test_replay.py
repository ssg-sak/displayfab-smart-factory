from datetime import datetime, timedelta, timezone

from app.enums import AlarmCode


def test_export_unknown_panel(client):
    res = client.get("/api/lab/export/PNL-99999")
    assert res.status_code == 404


def test_replay_empty_events(client):
    res = client.post("/api/lab/replay", json={"events": []})
    assert res.status_code == 400


def test_export_after_oled_happy(client):
    run = client.post("/api/lab/scenarios/oled_happy/run").json()
    glass = run["glass"]
    exported = client.get("/api/lab/export/" + glass).json()
    assert exported["count"] == 5
    assert [row["process_step"] for row in exported["events"]] == ["LOAD", "CLEAN", "EVAP", "ENCAP", "INSPECT"]


def test_replay_onto_wait_panel(client):
    run = client.post("/api/lab/scenarios/oled_happy/run").json()
    events = client.get("/api/lab/export/" + run["glass"]).json()["events"]
    res = client.post(
        "/api/lab/replay",
        json={
            "events": events,
            "refresh_timestamps": True,
            "lot_id": "LOT-20260918-001",
            "panel_id": "PNL-00005",
        },
    )
    body = res.json()
    assert res.status_code == 200
    assert body["ok"] is True
    assert body["accepted"] == 5
    assert body["rejected"] == 0
    history = client.get("/api/panels/PNL-00005/history").json()
    assert [h["process_step"] for h in history] == ["LOAD", "CLEAN", "EVAP", "ENCAP", "INSPECT"]


def test_replay_same_panel_rejected(client):
    run = client.post("/api/lab/scenarios/oled_happy/run").json()
    events = client.get("/api/lab/export/" + run["glass"]).json()["events"]
    res = client.post(
        "/api/lab/replay",
        json={
            "events": events,
            "refresh_timestamps": True,
            "lot_id": run["results"][0].get("lot_id", "LOT-20260918-001"),
            "panel_id": run["glass"],
        },
    )
    body = res.json()
    assert body["ok"] is True
    assert body["rejected"] >= 1
    assert body["accepted"] < body["count"]


def test_replay_stale_without_refresh(client):
    old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    events = [
        {
            "equipment_id": "LOAD-01",
            "event_type": "PROCESS",
            "lot_id": "LOT-20260918-001",
            "panel_id": "PNL-00005",
            "process_step": "LOAD",
            "recipe_id": "RCP-OLED-A01",
            "equipment_status": "RUN",
            "chamber_temperature": 118.4,
            "vacuum_pressure": 0.0041,
            "timestamp": old,
        }
    ]
    res = client.post(
        "/api/lab/replay",
        json={"events": events, "refresh_timestamps": False},
    )
    body = res.json()
    assert body["ok"] is True
    assert body["accepted"] == 0
    assert body["results"][0]["reason"] == AlarmCode.STALE_TIMESTAMP.value
