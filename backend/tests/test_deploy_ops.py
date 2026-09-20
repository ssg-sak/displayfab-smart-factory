"""공개 배포에만 켜지는 기능들. 로컬 기본값은 전부 꺼져 있어야 한다."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.config import as_sqlalchemy_url, settings
from app.models import Alarm, Lot, Panel, ProcessEvent, WorkOrder
from app.services.demo_pilot import ROTATION
from app.services.maintenance import reset_demo_data
from app.services.ratelimit import WriteRateLimiter, client_key
from app.services.scenarios import CATALOG
from tests.conftest import clean_glass, load_glass


def test_demo_features_off_by_default():
    assert settings.demo_autopilot is False
    assert settings.write_rate_per_min == 0
    assert settings.admin_token == ""


def test_reset_clears_today_and_restores_sample_lots(client, db_session):
    load_glass(client)
    clean_glass(client)
    client.post("/api/work-orders", json={"product_type": "OLED", "recipe_id": "RCP-OLED-A01", "qty": 1})
    assert db_session.query(ProcessEvent).count() > 0
    assert db_session.query(WorkOrder).count() > 0

    result = reset_demo_data(db_session)

    assert result["ok"] is True
    assert result["deleted_total"] > 0
    assert db_session.query(ProcessEvent).count() == 0
    assert db_session.query(Alarm).count() == 0
    assert db_session.query(WorkOrder).count() == 0
    # 연습용 카세트 3개와 유리 15장은 다시 깔린다.
    assert db_session.query(Lot).count() == 3
    assert db_session.query(Panel).count() == 15


def test_reset_keeps_masters_and_puts_equipment_back_offline(client, db_session):
    load_glass(client)
    reset_demo_data(db_session)

    rows = client.get("/api/equipment").json()
    assert len(rows) == 8
    assert all(row["connection_status"] == "OFFLINE" for row in rows)
    assert all(row["equipment_status"] == "IDLE" for row in rows)
    assert len(client.get("/api/lots").json()) == 3


def test_reset_api_hidden_without_token(client):
    assert client.post("/api/lab/reset").status_code == 404


def test_reset_api_needs_matching_token(client, monkeypatch):
    # HTTP 헤더는 ASCII만 실을 수 있어서 열쇠도 ASCII다.
    monkeypatch.setattr(settings, "admin_token", "demo-reset-key")

    assert client.post("/api/lab/reset").status_code == 403
    assert client.post("/api/lab/reset", headers={"X-Admin-Token": "wrong-key"}).status_code == 403

    ok = client.post("/api/lab/reset", headers={"X-Admin-Token": "demo-reset-key"})
    assert ok.status_code == 200
    assert ok.json()["ok"] is True


def test_health_reports_demo_mode(client):
    assert client.get("/api/health").json()["demo_autopilot"] is False


def test_rate_limiter_counts_per_client():
    limiter = WriteRateLimiter(per_minute=2)

    assert limiter.allow("1.1.1.1", now=0) is True
    assert limiter.allow("1.1.1.1", now=1) is True
    assert limiter.allow("1.1.1.1", now=2) is False
    # 다른 사람은 막히지 않는다.
    assert limiter.allow("2.2.2.2", now=2) is True
    # 1분이 지나면 다시 열린다.
    assert limiter.allow("1.1.1.1", now=61) is True


def test_rate_limiter_zero_means_unlimited():
    limiter = WriteRateLimiter(per_minute=0)
    assert all(limiter.allow("1.1.1.1", now=i) for i in range(100))


def test_client_key_prefers_proxy_header():
    assert client_key({"X-Forwarded-For": "203.0.113.9, 10.0.0.1"}, "10.0.0.1") == "203.0.113.9"
    assert client_key({}, "10.0.0.2") == "10.0.0.2"
    assert client_key({}, None) == "unknown"


def test_hosting_postgres_url_becomes_psycopg():
    assert as_sqlalchemy_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert (
        as_sqlalchemy_url("postgresql://u:p@h/db?sslmode=require")
        == "postgresql+psycopg://u:p@h/db?sslmode=require"
    )
    already = "postgresql+psycopg://u:p@h/db"
    assert as_sqlalchemy_url(already) == already


def test_autopilot_rotation_uses_real_scenarios():
    ids = {row["id"] for row in CATALOG}
    assert set(ROTATION) <= ids
    assert "heartbeat" in ids


@pytest.mark.parametrize("source", ["http", "autopilot"])
def test_reset_waits_for_inflight_work_order(client, monkeypatch, source):
    """Reproduce reset overlapping a multi-commit scenario, from either caller."""
    from app.api import lab
    from app.main import app
    from app.services.demo_pilot import run_locked
    from app.services.work_orders import create_and_release

    started = Event()
    release = Event()
    reset_requested = Event()
    reset_entered = Event()
    original_reset = lab.reset_demo_data
    monkeypatch.setattr(settings, "admin_token", "concurrency-test")

    def work(db):
        order, _ = create_and_release(
            db, product_type="OLED", recipe_id="RCP-OLED-A01", qty=1
        )
        started.set()
        assert release.wait(5), "test did not release the running scenario"
        # With the old implementation reset has deleted this committed row.
        db.refresh(order)
        return {"ok": True, "work_order_id": order.id}

    def reset(db):
        reset_entered.set()
        return original_reset(db)

    def request_reset():
        reset_requested.set()
        return client.post("/api/lab/reset", headers={"X-Admin-Token": "concurrency-test"})

    monkeypatch.setattr(lab, "reset_demo_data", reset)
    monkeypatch.setattr(lab, "run_scenario", lambda db, _: work(db))
    with ThreadPoolExecutor(max_workers=2) as pool:
        if source == "http":
            running = pool.submit(client.post, "/api/lab/scenarios/demo_oled_pass/run")
        else:
            running = client.portal.start_task_soon(run_locked, app.state.write_lock, work)
        try:
            assert started.wait(5)
            resetting = pool.submit(request_reset)
            assert reset_requested.wait(5)
            assert not reset_entered.wait(0.2), "reset overlapped the running scenario"
            # The health check must not wait for a long-running write.
            assert client.get("/api/health").status_code == 200
        finally:
            release.set()
        result = running.result(timeout=5)
        if source == "http":
            assert result.status_code == 200
            result = result.json()
        assert result["ok"] is True
        assert resetting.result(timeout=5).status_code == 200
    assert reset_entered.is_set()
    assert len(client.get("/api/lots").json()) == 3
