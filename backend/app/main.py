import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from app.services.demo_pilot import autopilot_loop
from app.services.offline import mark_offline_equipment
from app.services.ratelimit import WriteRateLimiter, client_key

logger = get_logger(__name__)
write_limiter = WriteRateLimiter(settings.write_rate_per_min)


def check_offline() -> None:
    db = SessionLocal()
    try:
        mark_offline_equipment(db)
    finally:
        db.close()


async def offline_loop(write_lock: asyncio.Lock) -> None:
    while True:
        await asyncio.sleep(settings.offline_check_interval_sec)
        try:
            async with write_lock:
                await asyncio.to_thread(check_offline)
        except Exception:
            logger.exception("offline detector failed")


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
    app.state.write_lock = asyncio.Lock()
    tasks = [asyncio.create_task(offline_loop(app.state.write_lock))]
    if settings.demo_autopilot and not settings.testing:
        tasks.append(asyncio.create_task(autopilot_loop(app.state.write_lock)))
    logger.info("DisplayFab Ops Lab started (educational simulator, not a real MES/CIM)")
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
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


@app.middleware("http")
async def serialize_writes(request: Request, call_next):
    # A scenario commits several times. Reset must wait for the whole request,
    # not just one transaction. Reads (especially health checks) stay available.
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return await call_next(request)
    async with request.app.state.write_lock:
        return await call_next(request)


@app.middleware("http")
async def write_rate_limit(request: Request, call_next):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return await call_next(request)
    key = client_key(request.headers, request.client.host if request.client else None)
    if not write_limiter.allow(key):
        retry = write_limiter.retry_after(key)
        logger.warning("write rate limit hit key=%s path=%s", key, request.url.path)
        return JSONResponse(
            status_code=429,
            content={"detail": f"요청이 너무 많습니다. {retry}초 뒤에 다시 시도하세요."},
            headers={"Retry-After": str(retry)},
        )
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
