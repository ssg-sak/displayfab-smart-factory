import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.logging_setup import bind_request_id
from app.schemas import EquipmentEventIn, EventIngestOut
from app.services.collector import collect_push
from app.services.dispatch import panel_dispatch
from app.models import Panel

router = APIRouter(tags=["events"])


@router.post("/events", response_model=EventIngestOut)
def post_event(
    payload: EquipmentEventIn,
    db: Session = Depends(get_db),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    force_db_failure: bool = Query(default=False),
) -> EventIngestOut:
    request_id = x_request_id or str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    bind_request_id(request_id)
    if force_db_failure:
        payload.force_db_failure = True

    accepted, reason, alarms, lot_status = collect_push(db, payload, request_id, event_id)

    if reason == "DB_WRITE_FAILURE":
        raise HTTPException(
            status_code=500,
            detail={
                "accepted": False,
                "event_id": event_id,
                "request_id": request_id,
                "reason": reason,
            },
        )

    next_step = None
    next_equipment_id = None
    if payload.panel_id:
        panel = db.get(Panel, payload.panel_id)
        if panel is not None:
            info = panel_dispatch(db, panel)
            next_step = info["next_step"]
            next_equipment_id = info["next_equipment_id"]

    return EventIngestOut(
        accepted=accepted,
        event_id=event_id,
        request_id=request_id,
        reason=reason,
        lot_status=lot_status,
        next_step=next_step,
        next_equipment_id=next_equipment_id,
        alarms=alarms,
    )
