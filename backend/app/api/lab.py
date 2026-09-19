from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Panel
from app.schemas import ReplayIn
from app.services.line_runner import run_work_order
from app.services.replay import export_panel_events, replay_events
from app.services.scenarios import CATALOG, run_scenario

router = APIRouter(prefix="/lab", tags=["lab"])


@router.get("/scenarios")
def list_scenarios() -> list[dict]:
    return CATALOG


@router.post("/scenarios/{scenario_id}/run")
def post_scenario(scenario_id: str, db: Session = Depends(get_db)) -> dict:
    result = run_scenario(db, scenario_id)
    if not result.get("ok") and result.get("error", "").startswith("unknown"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/export/{panel_id}")
def export_panel(panel_id: str, db: Session = Depends(get_db)) -> dict:
    if db.get(Panel, panel_id) is None:
        raise HTTPException(status_code=404, detail="Panel not found")
    events = export_panel_events(db, panel_id)
    return {"panel_id": panel_id, "count": len(events), "events": events}


@router.post("/run-order/{work_order_id}")
def post_run_order(work_order_id: str, db: Session = Depends(get_db)) -> dict:
    result = run_work_order(db, work_order_id)
    if not result.get("ok") and result.get("error", "").startswith("지시 없음"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/replay")
def post_replay(payload: ReplayIn, db: Session = Depends(get_db)) -> dict:
    result = replay_events(
        db,
        payload.events,
        refresh_timestamps=payload.refresh_timestamps,
        lot_id=payload.lot_id,
        panel_id=payload.panel_id,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result
