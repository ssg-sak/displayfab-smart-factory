# OEE

구현 위치: `backend/app/services/oee.py`, `GET /api/analytics/oee`, 생산 화면 5번 칸.

공식: Availability × Performance × Quality.

```text
Availability  (계획가동시간 - 정지시간) / 계획가동시간
              정지시간 = equipment_downtime (COMMUNICATION_LOSS / STOP / MAINTENANCE)
Performance   이론 사이클 합 / 가동시간
              이론 사이클 = domain/rules.IDEAL_CYCLE_SEC (시뮬레이터가 보고하는 값과 같은 표)
Quality       COMPLETE / (COMPLETE + FAIL + SCRAP)
              유리 단위로 센다. 한 장이 설비 다섯 대를 지나도 한 장이다
```

## 계획가동시간을 어디서 가져오는가

이 프로젝트에는 교대 근무표가 없다. 그래서 두 가지 중 하나를 쓴다.

```text
DISPLAYFAB_OEE_PLANNED_MINUTES > 0   지금부터 거꾸로 그 시간
0 (기본)                              오늘 설비가 처음 보고한 시각부터 지금까지
오늘 보고가 없으면                     "라인이 오늘 열리지 않았다". OEE를 내지 않는다
```

응답의 `planned_basis`에 어느 기준을 썼는지 항상 같이 나온다.

## 낼 수 없는 것은 null로 둔다

```text
실적이 없으면          performance = null
판정된 유리가 없으면    quality = null
라인이 안 열렸으면      availability = null
```

세 개 중 하나라도 null이면 `oee`도 null이고, 이유가 `missing`에 문장으로 들어간다.
숫자를 채우기 위해 가짜 가동시간이나 가짜 사이클을 만들지 않는다.

## 면접에서 말할 한 줄

> 정지시간은 통신 끊김·정지·정비를 구간으로 남긴 `equipment_downtime`에서, 이론 사이클은
> 시뮬레이터와 공유하는 표에서, 품질은 유리 판정에서 옵니다. 계획가동시간만 현장 값이
> 없어서 이 시스템이 정한 기준을 쓰고, 그 기준을 응답에 같이 내보냅니다.
