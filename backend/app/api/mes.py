from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MesBoardOut
from app.services.mes import mes_board

router = APIRouter(prefix="/mes", tags=["mes"])


@router.get("/board", response_model=MesBoardOut)
def get_mes_board(db: Session = Depends(get_db)) -> MesBoardOut:
    return mes_board(db)
