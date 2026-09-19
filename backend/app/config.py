"""학습용 설정. 여기 숫자는 실제 OLED/LCD 제조사양이 아니다."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "postgresql+psycopg://displayfab:displayfab@127.0.0.1:5435/displayfab"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DISPLAYFAB_",
        extra="ignore",
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
    )

    app_name: str = "DisplayFab Ops Lab"
    database_url: str = DEFAULT_DATABASE_URL
    testing: bool = False

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


settings = Settings()


def uses_sqlite(url: str | None = None) -> bool:
    return (url or settings.database_url).startswith("sqlite")
