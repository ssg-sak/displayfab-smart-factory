from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.enums import ConnectionStatus
from app.models import Alarm, Equipment
from app.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    db.execute(text("SELECT 1"))
    online = (
        db.query(Equipment)
        .filter(Equipment.connection_status == ConnectionStatus.ONLINE.value)
        .count()
    )
    total = db.query(Equipment).count()
    open_alarms = db.query(Alarm).filter(Alarm.resolved_at.is_(None)).count()
    return HealthOut(
        status="ok",
        db="ok",
        equipment_online=online,
        equipment_offline=total - online,
        open_alarms=open_alarms,
        demo_autopilot=settings.demo_autopilot,
    )
