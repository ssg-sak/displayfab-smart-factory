from collections.abc import Generator
from time import sleep

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings, uses_sqlite


class Base(DeclarativeBase):
    pass


def create_db_engine(url: str) -> Engine:
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if uses_sqlite(url):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_engine(url, **kwargs)


engine = create_db_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _bind_is_sqlite() -> bool:
    return engine.dialect.name == "sqlite"


def init_db() -> None:
    from app import models  # noqa: F401

    last_error: OperationalError | None = None
    attempts = 1 if _bind_is_sqlite() or settings.testing else 20
    for attempt in range(1, attempts + 1):
        try:
            _init_schema()
            return
        except OperationalError as exc:
            last_error = exc
            if attempt == attempts:
                break
            sleep(0.5)
    raise RuntimeError(
        "PostgreSQL에 연결할 수 없습니다. 프로젝트 루트에서 `docker compose up -d` 를 먼저 실행하세요."
    ) from last_error


def _init_schema() -> None:
    inspector = inspect(engine)
    if _bind_is_sqlite():
        needs_reset = False
        if inspector.has_table("process_event"):
            cols = {c["name"] for c in inspector.get_columns("process_event")}
            if "event_type" not in cols or not inspector.has_table("event_log"):
                needs_reset = True
        if inspector.has_table("lot"):
            lot_cols = {c["name"] for c in inspector.get_columns("lot")}
            if "product_type" not in lot_cols or "cassette_id" not in lot_cols:
                needs_reset = True
        if needs_reset:
            Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    timestamp_type = "DATETIME" if _bind_is_sqlite() else "TIMESTAMP"
    _add_column_if_missing("equipment", "current_recipe_id", "VARCHAR(64)")
    _add_column_if_missing("equipment", "interface_type", "VARCHAR(32) DEFAULT 'simulator'")
    _add_column_if_missing("equipment", "interface_endpoint", "VARCHAR(255)")
    _add_column_if_missing("host_command", "interface_type", "VARCHAR(32)")
    _add_column_if_missing("host_command", "delivered_at", timestamp_type)


def _add_column_if_missing(table: str, column: str, ddl: str) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(table):
        return
    cols = {c["name"] for c in inspector.get_columns(table)}
    if column in cols:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
