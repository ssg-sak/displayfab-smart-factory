"""학습용 설정. 여기 숫자는 실제 OLED/LCD 제조사양이 아니다."""

import os
import sys
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "postgresql+psycopg://displayfab:displayfab@127.0.0.1:5435/displayfab"


def as_sqlalchemy_url(url: str) -> str:
    """호스팅이 주는 postgres:// / postgresql:// 를 SQLAlchemy + psycopg 형식으로 맞춘다."""

    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _env_file() -> str | None:
    """pytest는 로컬 .env(공개 시연용 값)를 읽지 않는다."""

    if "pytest" in sys.modules or os.getenv("DISPLAYFAB_TESTING") == "1":
        return None
    path = ROOT_DIR / ".env"
    return str(path) if path.exists() else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DISPLAYFAB_",
        extra="ignore",
        env_file=_env_file(),
        env_file_encoding="utf-8",
    )

    app_name: str = "DisplayFab Ops Lab"
    database_url: str = DEFAULT_DATABASE_URL
    testing: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return as_sqlalchemy_url(value)

    # FAULT 1: 이 시간 동안 데이터가 없으면 OFFLINE
    communication_timeout_sec: int = 10
    offline_check_interval_sec: int = 2

    # FAULT 8: 이벤트 시각이 이보다 오래되면 STALE
    stale_event_threshold_sec: int = 60
    future_event_tolerance_sec: int = 30

    # 온도가 Recipe 허용폭 대비 이 비율 이상 벗어나면 CRITICAL
    sensor_critical_deviation_ratio: float = 0.20

    # OEE 계획가동시간. 이 시스템이 정한 기준이고 현장 교대시간이 아니다.
    # 0이면 "오늘 00:00부터 지금까지"를 계획시간으로 본다.
    oee_planned_minutes: int = 0

    log_level: str = "INFO"

    # 공개 서버용. 로컬에서는 전부 꺼져 있고, 켤 때만 동작한다.
    # 아무도 보고 있지 않은 서버는 설비가 보고를 올리지 않아 화면이 죽어 보인다.
    # 그래서 공개 배포에서만 서버가 설비 클라이언트 역할을 대신한다.
    demo_autopilot: bool = False
    demo_heartbeat_sec: int = 6
    demo_run_interval_sec: int = 30
    demo_reset_minutes: int = 60

    # 쓰기 요청 분당 상한. 0이면 제한 없음(로컬 기본값).
    write_rate_per_min: int = 0

    # 초기화 API 열쇠. 비어 있으면 그 API 자체가 없다.
    admin_token: str = ""


settings = (
    Settings(
        testing=True,
        demo_autopilot=False,
        write_rate_per_min=0,
        admin_token="",
        database_url="sqlite://",
    )
    if "pytest" in sys.modules or os.getenv("DISPLAYFAB_TESTING") == "1"
    else Settings()
)


def uses_sqlite(url: str | None = None) -> bool:
    return (url or settings.database_url).startswith("sqlite")
