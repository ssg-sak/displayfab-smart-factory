from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lot, Panel
from app.schemas import DiagnosisOut, DispatchOut, LotOut, ProcessHistoryItem, SlotMapOut, SlotOut, TravelerOut
from app.services.diagnosis import diagnose_lot
from app.services.dispatch import lot_dispatch
from app.services.history import lot_history, lot_traveler

router = APIRouter(prefix="/lots", tags=["lots"])


def _to_out(db: Session, row: Lot) -> LotOut:
    panel_count = db.query(Panel).filter(Panel.lot_id == row.id).count()
    return LotOut(
        id=row.id,
        cassette_id=row.cassette_id,
        product_type=row.product_type,
        expected_recipe_id=row.expected_recipe_id,
        status=row.status,
        current_equipment_id=row.current_equipment_id,
        current_step=row.current_step,
        hold_reason=row.hold_reason,
        panel_count=panel_count,
    )


@router.get("", response_model=list[LotOut])
def list_lots(db: Session = Depends(get_db)) -> list[LotOut]:
    rows = db.query(Lot).order_by(Lot.id.asc()).all()
    return [_to_out(db, row) for row in rows]


@router.get("/{lot_id}", response_model=LotOut)
def get_lot(lot_id: str, db: Session = Depends(get_db)) -> LotOut:
    row = db.get(Lot, lot_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Lot not found")
    return _to_out(db, row)


@router.get("/{lot_id}/dispatch", response_model=DispatchOut)
def get_lot_dispatch(lot_id: str, db: Session = Depends(get_db)) -> DispatchOut:
    row = db.get(Lot, lot_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Lot not found")
    info = lot_dispatch(db, row)
    if info is None:
        raise HTTPException(status_code=404, detail="No glass in lot")
    return DispatchOut(**info)


@router.get("/{lot_id}/slots", response_model=SlotMapOut)
def get_lot_slots(lot_id: str, db: Session = Depends(get_db)) -> SlotMapOut:
    row = db.get(Lot, lot_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Lot not found")
    panels = db.query(Panel).filter(Panel.lot_id == lot_id).order_by(Panel.slot_no.asc()).all()
    return SlotMapOut(
        lot_id=row.id,
        cassette_id=row.cassette_id,
        product_type=row.product_type,
        recipe_id=row.expected_recipe_id,
        status=row.status,
        slots=[SlotOut(slot_no=p.slot_no, panel_id=p.id, status=p.status) for p in panels],
    )


@router.get("/{lot_id}/traveler", response_model=TravelerOut)
def get_lot_traveler(lot_id: str, db: Session = Depends(get_db)) -> TravelerOut:
    row = db.get(Lot, lot_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Lot not found")
    return lot_traveler(db, row)


@router.get("/{lot_id}/history", response_model=list[ProcessHistoryItem])
def get_lot_history(lot_id: str, db: Session = Depends(get_db)) -> list[ProcessHistoryItem]:
    if db.get(Lot, lot_id) is None:
        raise HTTPException(status_code=404, detail="Lot not found")
    return lot_history(db, lot_id)


@router.get("/{lot_id}/diagnosis", response_model=DiagnosisOut)
def get_lot_diagnosis(lot_id: str, db: Session = Depends(get_db)) -> DiagnosisOut:
    row = db.get(Lot, lot_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Lot not found")
    return diagnose_lot(db, row)
