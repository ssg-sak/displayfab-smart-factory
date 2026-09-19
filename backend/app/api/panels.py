from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Panel
from app.schemas import DispatchOut, ProcessHistoryItem
from app.services.dispatch import panel_dispatch
from app.services.history import panel_history

router = APIRouter(prefix="/panels", tags=["panels"])


@router.get("/{panel_id}/dispatch", response_model=DispatchOut)
def get_panel_dispatch(panel_id: str, db: Session = Depends(get_db)) -> DispatchOut:
    panel = db.get(Panel, panel_id)
    if panel is None:
        raise HTTPException(status_code=404, detail="Panel not found")
    return DispatchOut(**panel_dispatch(db, panel))


@router.get("/{panel_id}/history", response_model=list[ProcessHistoryItem])
def get_panel_history(panel_id: str, db: Session = Depends(get_db)) -> list[ProcessHistoryItem]:
    if db.get(Panel, panel_id) is None:
        raise HTTPException(status_code=404, detail="Panel not found")
    return panel_history(db, panel_id)
