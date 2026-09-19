from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AnomalyOut, OeeOut
from app.services.anomaly import line_anomaly
from app.services.oee import line_oee

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/oee", response_model=OeeOut)
def get_oee(db: Session = Depends(get_db)) -> OeeOut:
    """OEE 조회. 분석은 설비를 직접 제어하지 않는다. 숫자만 낸다."""
    return OeeOut(**line_oee(db))


@router.get("/anomaly", response_model=AnomalyOut)
def get_anomaly(db: Session = Depends(get_db)) -> AnomalyOut:
    """텔레메트리 이상 점수. 읽기만 한다. 알람·명령은 사람/MES가 낸다."""
    return AnomalyOut(**line_anomaly(db))
