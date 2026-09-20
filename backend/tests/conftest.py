"""테스트는 프로세스에 남은 공개 시연 환경변수를 읽지 않는다."""

import os

for _key in list(os.environ):
    if _key.startswith("DISPLAYFAB_"):
        os.environ.pop(_key, None)
os.environ["DISPLAYFAB_TESTING"] = "1"

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database as database_module
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.seed import seed_if_empty
import app.main as main_module

# pytest는 Docker PostgreSQL 없이 돈다. 호스트 운영 DB는 PostgreSQL.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "testing", True)
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", TestSession)
    monkeypatch.setattr(main_module, "SessionLocal", TestSession)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_db = TestSession()
    seed_if_empty(seed_db)
    seed_db.close()

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        for eq_id in [
            "LOAD-01",
            "CLEAN-01",
            "PROC-01",
            "PROC-02",
            "ENC-01",
            "PI-01",
            "LCD-01",
            "INSPECT-01",
        ]:
            test_client.post("/api/commands", json={"command_type": "START", "equipment_id": eq_id})
        for eq_id in ["CLEAN-01", "PROC-01", "PROC-02", "ENC-01"]:
            test_client.post(
                "/api/commands",
                json={"command_type": "SELECT_RECIPE", "equipment_id": eq_id, "recipe_id": "RCP-OLED-A01"},
            )
        for eq_id in ["PI-01", "LCD-01"]:
            test_client.post(
                "/api/commands",
                json={"command_type": "SELECT_RECIPE", "equipment_id": eq_id, "recipe_id": "RCP-LCD-C01"},
            )
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(client):
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


def utc_ts(offset_sec: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_sec)).isoformat()


def make_event(**overrides):
    payload = {
        "equipment_id": "PROC-01",
        "event_type": "PROCESS",
        "lot_id": "LOT-20260918-001",
        "panel_id": "PNL-00001",
        "process_step": "EVAP",
        "recipe_id": "RCP-OLED-A01",
        "equipment_status": "RUN",
        "chamber_temperature": 118.4,
        "vacuum_pressure": 0.0041,
        "cycle_time_sec": 47.2,
        "alarm_code": None,
        "timestamp": utc_ts(),
    }
    payload.update(overrides)
    return payload


def load_glass(client, lot_id="LOT-20260918-001", panel_id="PNL-00001", recipe_id="RCP-OLED-A01", offset=-8):
    extras = {}
    if recipe_id.startswith("RCP-LCD"):
        extras = {"chamber_temperature": 88.0, "vacuum_pressure": 1.0}
    return client.post(
        "/api/events",
        json=make_event(
            equipment_id="LOAD-01",
            process_step="LOAD",
            lot_id=lot_id,
            panel_id=panel_id,
            recipe_id=recipe_id,
            timestamp=utc_ts(offset),
            **extras,
        ),
    )


def clean_glass(client, lot_id="LOT-20260918-001", panel_id="PNL-00001", recipe_id="RCP-OLED-A01", offset=-7):
    return client.post(
        "/api/events",
        json=make_event(
            equipment_id="CLEAN-01",
            process_step="CLEAN",
            lot_id=lot_id,
            panel_id=panel_id,
            recipe_id=recipe_id,
            timestamp=utc_ts(offset),
        ),
    )


def select_recipe(client, equipment_id, recipe_id):
    return client.post(
        "/api/commands",
        json={"command_type": "SELECT_RECIPE", "equipment_id": equipment_id, "recipe_id": recipe_id},
    )


def pi_glass(client, lot_id="LOT-20260918-003", panel_id="PNL-00011", recipe_id="RCP-LCD-C01", offset=-7):
    return client.post(
        "/api/events",
        json=make_event(
            equipment_id="PI-01",
            process_step="PI",
            lot_id=lot_id,
            panel_id=panel_id,
            recipe_id=recipe_id,
            chamber_temperature=88.0,
            vacuum_pressure=1.0,
            timestamp=utc_ts(offset),
        ),
    )
