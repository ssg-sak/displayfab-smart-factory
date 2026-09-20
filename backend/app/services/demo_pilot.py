"""공개 서버에서 라인을 살아 있게 유지한다.

로컬에서는 사람이 시뮬레이터를 켜서 설비 보고를 올린다. 공개 주소에는 그 시뮬레이터가
없으니, 아무도 안 보는 동안 설비가 전부 끊김으로 떨어져 고장난 화면이 된다.
그래서 이 서버가 설비 클라이언트 역할을 대신한다.

대신하는 방식은 화면 버튼과 똑같다. 수집 경로(collect_push)를 그대로 지나가므로
검증·알람·상태 판정이 전부 평소대로 돈다. 이 파일이 DB를 직접 고치는 곳은 없다.
`DISPLAYFAB_DEMO_AUTOPILOT=1` 일 때만 돈다.
"""

from __future__ import annotations

import asyncio
from itertools import cycle

from app import database
from app.config import settings
from app.logging_setup import get_logger
from app.services.maintenance import reset_demo_data
from app.services.scenarios import run_scenario

logger = get_logger(__name__)

# 합격만 계속 나오면 알람·품질 화면이 비어 보인다. 불량과 조건 틀림을 섞는다.
ROTATION = [
    "demo_oled_pass",
    "demo_lcd_pass",
    "demo_oled_pass",
    "demo_oled_fail",
    "demo_oled_pass",
    "demo_lcd_pass",
    "demo_recipe_mismatch",
]


def _in_session(work) -> dict:
    db = database.SessionLocal()
    try:
        return work(db)
    finally:
        db.close()


def _beat(_db) -> dict:
    return run_scenario(_db, "heartbeat")


async def run_locked(write_lock: asyncio.Lock, work) -> dict:
    """Use the same gate as HTTP writes, including manual reset requests."""
    async with write_lock:
        return await asyncio.to_thread(_in_session, work)


async def autopilot_loop(write_lock: asyncio.Lock) -> None:
    plan = cycle(ROTATION)
    beat_every = max(2, settings.demo_heartbeat_sec)
    run_every = max(beat_every, settings.demo_run_interval_sec)
    reset_every = max(60, settings.demo_reset_minutes * 60)
    logger.info(
        "demo autopilot on (heartbeat=%ds, run=%ds, reset=%ds)", beat_every, run_every, reset_every
    )

    since_run = 0
    since_reset = 0
    while True:
        await asyncio.sleep(beat_every)
        since_run += beat_every
        since_reset += beat_every

        if since_reset >= reset_every:
            since_reset = 0
            since_run = 0
            try:
                await run_locked(write_lock, reset_demo_data)
            except Exception:
                logger.exception("demo autopilot reset failed")

        try:
            await run_locked(write_lock, _beat)
        except Exception:
            logger.exception("demo autopilot heartbeat failed")

        if since_run >= run_every:
            since_run = 0
            scenario = next(plan)
            try:
                result = await run_locked(
                    write_lock, lambda db: run_scenario(db, scenario)
                )
                if not result.get("ok", True):
                    logger.warning("demo autopilot %s: %s", scenario, result.get("error"))
            except Exception:
                logger.exception("demo autopilot run failed (%s)", scenario)
