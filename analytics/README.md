# Analytics

KPI는 이미 호스트에 있다: `GET /api/kpis`, `backend/app/services/kpis.py`.

여기 폴더는 **아직 없는 분석만** 자리를 연다.

- `oee/` — Availability × Performance × Quality. 지금은 계산하지 않음
- `anomaly/` — 텔레메트리 이상탐지. 모델 없음

흐름 (미래):

```text
Telemetry → Feature → Model → Score → Alarm
Alarm → 사람/MES → POST /api/commands → (미래) Adapter
```

AI가 PLC/시뮬레이터를 직접 제어하지 않는다.
