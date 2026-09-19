from tests.conftest import utc_ts


def beat(client, temp, pressure=0.0041, equipment_id="PROC-01"):
    return client.post(
        "/api/events",
        json={
            "equipment_id": equipment_id,
            "event_type": "HEARTBEAT",
            "equipment_status": "IDLE",
            "chamber_temperature": temp,
            "vacuum_pressure": pressure,
            "timestamp": utc_ts(),
        },
    )


def test_anomaly_says_not_enough_data_before_samples(client):
    body = client.get("/api/analytics/anomaly").json()
    assert body["flagged"] == []
    proc = next(row for row in body["equipment"] if row["equipment_id"] == "PROC-01")
    assert proc["level"] == "데이터 부족"
    assert "학습 모델이 아니고" in body["note"]


def test_anomaly_stays_normal_on_steady_telemetry(client):
    for i in range(14):
        beat(client, 118.0 + (i % 2) * 0.2)
    body = client.get("/api/analytics/anomaly").json()
    proc = next(row for row in body["equipment"] if row["equipment_id"] == "PROC-01")
    assert proc["level"] == "정상"
    assert proc["samples"] >= 14
    assert body["flagged"] == []


def test_anomaly_flags_a_sudden_jump(client):
    for i in range(14):
        beat(client, 118.0 + (i % 2) * 0.2)
    beat(client, 140.0)
    body = client.get("/api/analytics/anomaly").json()
    proc = next(row for row in body["equipment"] if row["equipment_id"] == "PROC-01")
    assert proc["level"] == "경보"
    assert proc["temperature"]["sigma"] > 3
    assert "PROC-01" in body["flagged"]


def test_anomaly_is_read_only(client):
    for i in range(14):
        beat(client, 118.0 + (i % 2) * 0.2)
    beat(client, 140.0)
    before = len(client.get("/api/alarms").json())
    client.get("/api/analytics/anomaly")
    assert len(client.get("/api/alarms").json()) == before
    assert client.get("/api/equipment/PROC-01").json()["equipment_status"] != "STOP"
