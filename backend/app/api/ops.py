import asyncio
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain.rules import LCD_EQUIPMENT, LCD_ROUTE, OLED_EQUIPMENT, OLED_ROUTE
from app.models import EventLog
from app.schemas import EventLogOut, KpiOut, LineOut, ProductionOut, WipOut
from app.services.dispatch import line_wip
from app.services.production import today_production
from app.services.event_bus import subscribe, unsubscribe
from app.services.kpis import kpis

router = APIRouter(tags=["ops"])


@router.get("/kpis", response_model=KpiOut)
def get_kpis(db: Session = Depends(get_db)) -> KpiOut:
    return kpis(db)


@router.get("/line", response_model=LineOut)
def get_line() -> LineOut:
    return LineOut(
        oled_route=OLED_ROUTE,
        lcd_route=LCD_ROUTE,
        oled_equipment=OLED_EQUIPMENT,
        lcd_equipment=LCD_EQUIPMENT,
        note="연습용 축소 라인입니다. 증착은 PROC-01/02 중 빈 쪽으로 보냅니다.",
    )


@router.get("/production", response_model=ProductionOut)
def get_production(db: Session = Depends(get_db)) -> ProductionOut:
    return ProductionOut(**today_production(db))


@router.get("/wip", response_model=WipOut)
def get_wip(db: Session = Depends(get_db)) -> WipOut:
    return WipOut(**line_wip(db))


@router.get("/events/recent", response_model=list[EventLogOut])
def recent_events(db: Session = Depends(get_db), limit: int = Query(default=40, le=200)) -> list[EventLogOut]:
    return db.query(EventLog).order_by(EventLog.created_at.desc()).limit(limit).all()


@router.get("/stream")
async def stream_events():
    queue = subscribe()

    async def gen():
        try:
            yield "data: {\"type\":\"hello\"}\n\n"
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(item)}\n\n"
                except asyncio.TimeoutError:
                    yield "data: {\"type\":\"ping\"}\n\n"
        finally:
            unsubscribe(queue)

    return StreamingResponse(gen(), media_type="text/event-stream")
