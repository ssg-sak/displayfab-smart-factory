"""공개 시연 서버를 처음 상태로 되돌린다.

누구나 버튼을 누를 수 있는 주소에 올리면 데이터가 쌓이고 더러워진다.
마스터(설비·조건)는 남기고, 그날 생긴 거래 데이터만 지운 뒤 연습용 카세트를
다시 깐다. 로컬 개발에서는 호출되지 않는다.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.enums import ConnectionStatus, EquipmentStatus
from app.logging_setup import get_logger
from app.models import (
    Alarm,
    Equipment,
    EquipmentDowntime,
    EventLog,
    HostCommand,
    Lot,
    Panel,
    ProcessEvent,
    SensorReading,
    StateChange,
    Telemetry,
    WorkOrder,
)
from app.seed import ensure_masters, seed_sample_lots

logger = get_logger(__name__)

# 지우는 순서가 곧 외래키 순서다. 자식부터 지운다.
TRANSACTIONAL = (
    SensorReading,
    Telemetry,
    EquipmentDowntime,
    ProcessEvent,
    Alarm,
    EventLog,
    StateChange,
    HostCommand,
    WorkOrder,
    Panel,
    Lot,
)


def reset_demo_data(db: Session) -> dict:
    deleted: dict[str, int] = {}
    for model in TRANSACTIONAL:
        deleted[model.__tablename__] = db.query(model).delete(synchronize_session=False)

    for eq in db.query(Equipment).all():
        eq.equipment_status = EquipmentStatus.IDLE.value
        eq.connection_status = ConnectionStatus.OFFLINE.value
        eq.current_lot_id = None
        eq.current_recipe_id = None
        eq.last_seen_at = None
    db.commit()

    ensure_masters(db)
    seed_sample_lots(db)

    total = sum(deleted.values())
    logger.info("demo data reset (rows=%d)", total)
    return {"ok": True, "deleted": deleted, "deleted_total": total}
