"""텔레메트리 이상 점수. 학습 모델이 아니다.

수집된 telemetry의 평균·표준편차 대비 마지막 값이 몇 시그마인지만 낸다.
모르는 것을 아는 척하지 않는다. 표본이 적으면 "데이터 부족"으로 답한다.

분석은 설비를 직접 제어하지 않는다. 이 서비스는 읽기만 한다.
점수를 알람으로 올리는 것은 alarm_service, 명령을 내리는 것은 사람/MES다.
"""

from __future__ import annotations

from statistics import StatisticsError, mean, stdev

from sqlalchemy.orm import Session

from app.models import Equipment, Telemetry
from app.services.timeutil import utcnow

MIN_SAMPLES = 10
WATCH_SIGMA = 2.0
ALERT_SIGMA = 3.0


def _day_start():
    return utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def _score(values: list[float]) -> dict:
    latest = values[-1]
    if len(values) < MIN_SAMPLES:
        return {
            "latest": latest,
            "mean": round(mean(values), 4),
            "stdev": None,
            "sigma": None,
            "level": "데이터 부족",
        }
    baseline = values[:-1]
    try:
        spread = stdev(baseline)
    except StatisticsError:
        spread = 0.0
    center = mean(baseline)
    if spread <= 0:
        sigma = 0.0
    else:
        sigma = (latest - center) / spread
    level = "정상"
    if abs(sigma) >= ALERT_SIGMA:
        level = "경보"
    elif abs(sigma) >= WATCH_SIGMA:
        level = "주의"
    return {
        "latest": latest,
        "mean": round(center, 4),
        "stdev": round(spread, 4),
        "sigma": round(sigma, 2),
        "level": level,
    }


def equipment_anomaly(db: Session, equipment_id: str) -> dict:
    rows = (
        db.query(Telemetry)
        .filter(
            Telemetry.equipment_id == equipment_id,
            Telemetry.recorded_at >= _day_start(),
        )
        .order_by(Telemetry.recorded_at.asc(), Telemetry.id.asc())
        .all()
    )
    temps = [row.chamber_temperature for row in rows if row.chamber_temperature is not None]
    pressures = [row.vacuum_pressure for row in rows if row.vacuum_pressure is not None]
    out: dict = {
        "equipment_id": equipment_id,
        "samples": len(rows),
        "temperature": _score(temps) if temps else None,
        "pressure": _score(pressures) if pressures else None,
    }
    levels = [
        part["level"]
        for part in (out["temperature"], out["pressure"])
        if part is not None
    ]
    if "경보" in levels:
        out["level"] = "경보"
    elif "주의" in levels:
        out["level"] = "주의"
    elif "정상" in levels:
        out["level"] = "정상"
    else:
        out["level"] = "데이터 부족"
    return out


def line_anomaly(db: Session) -> dict:
    rows = [
        equipment_anomaly(db, eq.id)
        for eq in db.query(Equipment).order_by(Equipment.id.asc()).all()
    ]
    flagged = [row["equipment_id"] for row in rows if row["level"] in ("주의", "경보")]
    return {
        "date": _day_start().strftime("%Y-%m-%d"),
        "method": f"telemetry 평균·표준편차 대비 마지막 값의 시그마. 표본 {MIN_SAMPLES}개 미만은 판단하지 않는다.",
        "note": "통계 규칙이다. 학습 모델이 아니고 고장을 예측하지 않는다. 설비를 직접 제어하지 않는다.",
        "flagged": flagged,
        "equipment": rows,
    }
