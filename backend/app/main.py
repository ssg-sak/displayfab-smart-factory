import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    alarms,
    analytics,
    commands,
    equipment,
    events,
    health,
    lab,
    lots,
    mes,
    ops,
    panels,
    work_orders,
)
from app.config import settings
from app.database import SessionLocal, init_db
from app.logging_setup import bind_request_id, configure_logging, get_logger
from app.seed import seed_if_empty
from app.services.offline import mark_offline_equipment

logger = get_logger(__name__)


async def offline_loop() -> None:
    while True:
        await asyncio.sleep(settings.offline_check_interval_sec)
        db = SessionLocal()
        try:
            mark_offline_equipment(db)
        except Exception:
            logger.exception("offline detector failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    init_db()
    db = SessionLocal()
    try:
        if not settings.testing:
            seed_if_empty(db)
    finally:
        db.close()
    task = asyncio.create_task(offline_loop())
    logger.info("DisplayFab Ops Lab started (educational simulator, not a real MES/CIM)")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="DisplayFab Ops Lab",
    description=(
        "OLED/LCD 스마트팩토리 SW 구조 학습용 축소 모델. "
        "실제 생산설비, PLC, MES, CIM이 아니다."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    incoming = request.headers.get("X-Request-Id")
    bind_request_id(incoming or "-")
    return await call_next(request)


app.include_router(events.router, prefix="/api")
app.include_router(equipment.router, prefix="/api")
app.include_router(lots.router, prefix="/api")
app.include_router(panels.router, prefix="/api")
app.include_router(alarms.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(commands.router, prefix="/api")
app.include_router(ops.router, prefix="/api")
app.include_router(lab.router, prefix="/api")
app.include_router(work_orders.router, prefix="/api")
app.include_router(mes.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")

dashboard_dir = Path(__file__).resolve().parents[2] / "dashboard"
if dashboard_dir.exists():
    app.mount("/", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")
