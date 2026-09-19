# DisplayFab 스마트팩토리 — 구조

OLED/LCD 가상 라인 스마트팩토리 시스템.

설비가 실적과 생존신호를 올리고, 호스트가 지시·조건·인터록으로 라인을 돌리고,
불량이면 멈추고 이력을 추적한다.

설비는 가상이다. PLC 케이블은 없다.

```
설비  --실적·생존신호-->  호스트
호스트 --켜기·조건------>  설비
호스트 ---------------->  생산 · 운전
```

계층 지도·갭·Adapter 계약은 `ARCHITECTURE_LAYERS.md`.

각 섹션은 구현 이유를 남기기 위해
**WHY / FLOW / FAILURE / DEBUG** 를 붙인다.

---

## 1. 시스템 아키텍처

가상 설비는 JSON 이벤트를 HTTP로 보낸다.
서버는 검증 → 저장 → 상태갱신 → Alarm → 조회 API → Dashboard 순으로 처리한다.

```
[Python Simulator] ──┐
                     │  POST /api/events  (JSON)
[C# Simulator]     ──┘
                     │
                     ▼
              FastAPI (ingestion)
                     │
                     ▼
         Validation Pipeline
         (equipment / lot / panel /
          recipe / sensor / duplicate / stale)
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
     reject + Alarm        accept + persist
          │                     │
          │                     ▼
          │              PostgreSQL (SQLAlchemy)
          │                     │
          │         process_event / sensor_reading
          │         lot.status / equipment.status
          │                     │
          └──────────┬──────────┘
                     ▼
              Query APIs
                     │
                     ▼
              Dashboard (4 screens)

Background loop:
  last_seen + timeout → Connection OFFLINE + COMMUNICATION_LOSS
```

**왜 이렇게 단순한가**

이 시스템에서 만져볼 것은 메시지 버스가 아니다.

- 설비 데이터가 어디로 들어오는가
- 잘못된 데이터는 어디서 거르는가
- 상태는 어디에 남는가
- 화면이 비면 어디부터 보는가

이 경로를 한 줄로 그릴 수 있으면 된다.

**WHY:** 기본 단위는 “설비 보고 → 시스템 판단 → DB 기록 → 사람 조회”다.
**FLOW:** Simulator → HTTP → FastAPI → Validation → DB → API → UI
**FAILURE:** Simulator 미실행, 포트 오류, validation reject, DB lock, UI 폴링 실패
**DEBUG:** 로그의 `request_id`/`event_id`로 한 건을 끝까지 따라간다

---

## 2. 생산 흐름 (축소 모델)

복잡한 OLED/LCD 전 공정을 그대로 만들지 않는다.

OLED/LCD 축소 라우트:

```
OLED LOT / Cassette
  → LOAD-01  Cassette Loader
  → CLEAN-01 Pre-Clean
  → PROC-01/02  OLED Evaporation (educational)
  → ENC-01   OLED Encapsulation (educational)
  → INSPECT-01
  → COMPLETE

LCD LOT / Cassette
  → LOAD-01  Cassette Loader
  → PI-01    PI Coat
  → LCD-01   LCD Cell Process (educational)
  → INSPECT-01
  → COMPLETE
```

호스트는 PROCESS 전에 START와 SELECT_RECIPE(PPID)를 보낸다.
Cassette 슬롯맵은 `/api/lots/{id}/slots` 이다.

실제 Array/Cell/Module 전체 공정을 구현하지 않는다.
제품이 다른 설비로 들어가면 PRODUCT_ROUTE_VIOLATION 인터록이 걸린다.

이것은 **디스플레이 제조 SW의 흐름을 이해하기 위한 축소 모델**이다.
실제 제조공정과 동일하다고 말하면 안 된다.

한 OLED Glass의 이상적인 이력 예:

```
PNL-00001  CST-OLED-001
LOAD-01      LOAD
CLEAN-01     CLEAN       RCP-OLED-A01
PROC-01      RCP-OLED-A01  EVAP
ENC-01       ENCAP
INSPECT-01   PASS
```

**WHY:** 이력(traceability)을 보려면 최소 투입-공정-검사가 필요하다.
**FLOW:** LOT가 설비를 이동하며 process_event가 쌓인다.
**FAILURE:** 한 step 이벤트가 reject되면 이력이 비어 보인다.
**DEBUG:** 해당 panel_id의 process_event 건수와 서버 로그의 reject 사유를 본다.

---

## 3. Entity 관계

핵심 명사 10개를 테이블/상태로 대응한다.

| 개념 | 역할 |
|---|---|
| Equipment | 가상 설비. LOAD-01 / PROC-01 / INSPECT-01 |
| Lot | 함께 흐르는 Panel 묶음. Recipe가 지정됨 |
| Panel | 개별 기판. 이력이 남는 최소 추적 단위 |
| Process Step | LOAD / DEPOSITION / INSPECT |
| Recipe | 해당 공정에서 설비가 지켜야 하는 조건 세트 |
| Sensor Reading | 온도/압력 등 측정값 |
| Alarm | 정상 흐름에서 벗어난 사건 |
| Equipment State | IDLE/RUN/STOP/ERROR/MAINTENANCE + ONLINE/OFFLINE |
| Lot State | WAIT/PROCESSING/HOLD/COMPLETE |
| Process History | Panel/LOT 기준 process_event 시간순 목록 |

관계:

```
Recipe 1 ──< Lot
Lot    1 ──< Panel
Lot    1 ──< ProcessEvent
Panel  1 ──< ProcessEvent
Recipe 1 ──< ProcessEvent
Equipment 1 ──< ProcessEvent
Equipment 1 ──< Alarm
ProcessEvent 1 ── 1 SensorReading   (이번 Lab에서는 이벤트당 1건)
```

**WHY:** LOT는 작업 묶음, Panel/Glass는 추적 단위다. 테이블로 나눠야 이력이 남는다.
**FLOW:** 이벤트 1건이 Equipment/Lot/Panel/Recipe를 동시에 가리킨다.
**FAILURE:** FK가 없으면 유령 LOT/Panel이 저장된다. 너무 강한 FK는 UNKNOWN_EQUIPMENT Alarm을 못 남긴다.
**DEBUG:** 이벤트 저장 실패 시 FK violation인지 validation reject인지 로그로 구분한다.

---

## 4. DB Schema

PostgreSQL + SQLAlchemy. 호스트 운영 DB다. pytest는 인메모리 SQLite를 쓴다.

### 4.1 테이블

**equipment**
- id (PK, 예: PROC-01)
- name
- process_step
- equipment_status
- connection_status
- current_lot_id (nullable)
- current_recipe_id (nullable)
- last_seen_at (nullable)

**recipe**
- id (PK, 예: RCP-OLED-A01)
- name
- expected_temperature_min / max
- expected_pressure_min / max

> 임계값은 실제 OLED 제조사양이 아니다. `config`의 학습용 범위다.

**lot**
- id (PK)
- expected_recipe_id (FK recipe.id)
- status
- current_equipment_id (nullable)
- current_step (nullable)
- hold_reason (nullable)

**panel**
- id (PK)
- lot_id (FK lot.id)
- status

**process_event**
- id (PK, integer)
- event_id (unique, UUID)
- fingerprint (unique)
- equipment_id (FK)
- lot_id (FK)
- panel_id (FK)
- recipe_id (FK, nullable)
- process_step
- equipment_status
- cycle_time_sec
- event_timestamp
- received_at
- inspect_result (nullable, PASS/FAIL)

**sensor_reading**
- id (PK)
- process_event_id (FK, unique)
- equipment_id
- chamber_temperature
- vacuum_pressure
- recorded_at

**alarm**
- id (PK)
- alarm_id (unique, 예: ALM-1001)
- equipment_id (nullable — 미등록 설비도 문자열로 남김)
- lot_id (nullable)
- panel_id (nullable)
- event_id (nullable)
- alarm_code
- severity
- message
- occurred_at
- resolved_at (nullable)

### 4.2 INDEX

조회가 많은 축:

- 시간순 이력: `process_event(panel_id, event_timestamp)`
- LOT 이력: `process_event(lot_id, event_timestamp)`
- 설비 최근 이벤트: `process_event(equipment_id, event_timestamp)`
- Alarm 현황: `alarm(equipment_id, occurred_at)`, `alarm(alarm_code)`
- Offline 판단: `equipment(last_seen_at)`
- 중복 방지: `process_event(fingerprint)` UNIQUE

인덱스: 화면이 설비/LOT/Panel/시간으로 항상 찾기 때문이다.

**WHY:** 생산 모니터링은 insert도 많지만, 장애 순간에는 조건부 SELECT가 더 급하다.
**FLOW:** 이벤트 INSERT → 상태 UPDATE → 대시보드 SELECT
**FAILURE:** UNIQUE(fingerprint) 충돌 = 중복 이벤트
**DEBUG:** PostgreSQL에서 SQL 직접 조회로 API 결과와 비교한다.

---

## 5. State Model

문자열 리터럴을 코드 여기저기에서 비교하지 않는다.
`app/enums.py`가 단일 출처다.

### Equipment 상태

| 값 | 의미 (이 Lab에서) |
|---|---|
| IDLE | 이벤트 없음, 가동 대기 |
| RUN | 현재 공정 이벤트 처리 중 |
| STOP | 정상 정지 |
| ERROR | 설비 보고 상태가 ERROR |
| MAINTENANCE | 유지보수 |

### Connection 상태

| 값 | 의미 |
|---|---|
| ONLINE | timeout 안에 데이터가 들어옴 |
| OFFLINE | `COMMUNICATION_TIMEOUT_SEC`(기본 10초) 동안 데이터 없음 |

Equipment 상태와 Connection 상태는 다르다.
RUN이어도 OFFLINE일 수 있다. “마지막에 RUN이라고 보고한 뒤 통신이 끊긴 것”이다.

### Lot 상태

| 값 | 의미 |
|---|---|
| WAIT | 아직 투입 전 |
| PROCESSING | 유효 이벤트 수신 후 진행 중 |
| HOLD | Recipe mismatch 등, 시스템이 진행을 막음 |
| COMPLETE | INSPECT 단계까지 유효 이력 완료 |

### Alarm Severity

INFO / WARNING / CRITICAL

**WHY:** 화면의 “설비 빨강”이 통신 문제인지 공정 문제인지 나눠야 한다.
**FLOW:** 이벤트.equipment_status → Equipment.equipment_status, last_seen 갱신 → connection ONLINE
**FAILURE:** 상태 문자열 오타, HOLD인데 COMPLETE로 덮어씀
**DEBUG:** equipment / lot 테이블의 status 컬럼을 API 응답과 비교

---

## 6. Recipe Validation

이번 프로젝트에서 Recipe는

> 특정 공정을 수행할 때 설비가 사용해야 하는 조건 세트

예:

```
RCP-OLED-A01
  expected_temperature_min/max
  expected_pressure_min/max
```

LOT:

```
LOT-20260918-001.expected_recipe = RCP-OLED-A01
```

설비 보고 `recipe_id`가 다르면:

1. Alarm `RECIPE_MISMATCH` (CRITICAL)
2. LOT → HOLD
3. 이벤트는 이력으로 남긴다 (실제로 무엇을 보고했는지 추적해야 함)

목적은 “잘못된 공정 조건으로 생산이 진행되는 것을 시스템이 막는다”는 개념이다.

**WHY:** 제조 SW의 핵심 책임 중 하나가 잘못된 Recipe 적용을 막는 것이다.
**FLOW:** event.recipe_id vs lot.expected_recipe_id
**FAILURE:** LOT에 Recipe가 없거나, 설비가 recipe_id를 안 보냄
**DEBUG:** GET /api/lots/{id} 와 해당 시점 process_event.recipe_id 비교

---

## 7. Alarm Model

Alarm은 process_event와 별도 테이블이다.

정상 이력과 예외 이력을 같은 테이블에 넣으면
“오늘 무슨 일이 있었나”를 빠르게 못 본다.

필드:

- alarm_id
- equipment_id
- lot_id (optional)
- alarm_code
- severity
- message
- occurred_at
- resolved_at

예:

```
ALM-1001
equipment: PROC-01
code: RECIPE_MISMATCH
severity: CRITICAL
lot: LOT-20260918-001
message: Expected RCP-OLED-A01 but received RCP-OLED-B01
```

열린 Alarm: `resolved_at IS NULL`
통신 복구 시 `COMMUNICATION_LOSS`만 자동 resolve 한다.

**WHY:** 모니터링 화면 3번은 Alarm이다. 조회 패턴이 이력과 다르다.
**FLOW:** validation 실패/이탈 → alarm INSERT → Dashboard Alarm Monitor
**FAILURE:** Alarm만 있고 event가 없음(reject), 또는 event만 있고 Alarm 누락
**DEBUG:** 같은 event_id로 alarm / process_event / 로그를 조인해서 본다

---

## 8. Fault Scenario

반드시 구현하는 10개. reject는 저장하지 않고 Alarm만, accept-with-alarm은 둘 다 남긴다.

| ID | Code | 판단 | 처리 |
|---|---|---|---|
| F1 | COMMUNICATION_LOSS | last_seen이 N초 초과 | connection OFFLINE, Alarm |
| F2 | TEMPERATURE_OUT_OF_RANGE | Recipe 온도 범위 밖 | WARNING 또는 CRITICAL, 이벤트는 저장 |
| F3 | PRESSURE_OUT_OF_RANGE | Recipe 압력 범위 밖 | Alarm, 이벤트 저장 |
| F4 | RECIPE_MISMATCH | LOT Recipe ≠ 보고 Recipe | CRITICAL, LOT HOLD, 이벤트 저장 |
| F5 | INVALID_LOT | 없는 lot_id | reject + Alarm |
| F6 | INVALID_PANEL | LOT에 속하지 않은 panel | reject + Alarm |
| F7 | DUPLICATE_EVENT | 같은 fingerprint | reject + Alarm |
| F8 | STALE_TIMESTAMP | 너무 과거(또는 과도한 미래) | reject + Alarm |
| F9 | UNKNOWN_EQUIPMENT | 미등록 설비 | reject + Alarm |
| F10 | DB_WRITE_FAILURE | 테스트 플래그 | 500, Alarm, 저장 안 함 |

온도 CRITICAL 기준(학습용):
범위를 벗어난 뒤, 이탈폭이 허용폭의 20%를 넘으면 CRITICAL, 아니면 WARNING.

**WHY:** 기술지원 업무의 본질은 정상 경로가 아니라 이 10가지를 구분하는 것이다.
**FLOW:** Simulator `--fault` → 같은 POST 입구 → 다른 validation 가지
**FAILURE:** timeout이 너무 짧아 평상시에도 OFFLINE
**DEBUG:** TROUBLESHOOTING.md CASE A~D

---

## 9. 폴더 구조

```
display-ops-practice/
├── ARCHITECTURE.md          ← 이 문서 (설계)
├── README.md
├── TROUBLESHOOTING.md
├── INTERVIEW_NOTES.md       ← 개념 메모 (선택)
├── SQL_PRACTICE.md
├── .gitignore
├── config/
│   └── settings.py          ← 학습용 임계값 (실제 스펙 아님)
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── enums.py         ← 상태값 단일 출처
│   │   ├── logging_setup.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── seed.py
│   │   ├── api/             ← HTTP 입구
│   │   └── services/        ← 검증/Alarm/상태/Offline
│   └── tests/
├── simulator/
│   └── python_simulator.py
├── csharp_simulator/        ← PHASE 16
├── dashboard/               ← 4화면, 디자인 최소화
└── sql/
    └── interview_queries.sql
```

MVP에 넣지 않는 것: Kafka, Kubernetes, Microservice, Event Bus, 딥러닝, CV, 실제 PLC 프로토콜, 과도한 UI.

---

## 10. Phase별 구현 계획

| Phase | 내용 | 완료 기준 |
|---|---|---|
| 0 | 이 설계 문서 | 테이블/상태/Fault가 글으로 고정됨 |
| 1 | Equipment/Recipe/Lot/Panel seed | 서버 기동 시 3설비 2Recipe 샘플 LOT |
| 2 | POST /api/events | JSON 수신, request_id 부여 |
| 3 | Python Simulator | 3설비를 따라가며 POST |
| 4 | Process Event 저장 | process_event + sensor_reading INSERT |
| 5 | Recipe Validation | mismatch → HOLD |
| 6 | Sensor Range | 온도/압력 Alarm |
| 7 | Alarm 테이블/API | /api/alarms |
| 8 | LOT State | WAIT/PROCESSING/HOLD/COMPLETE |
| 9 | Panel Traceability | /api/panels/{id}/history |
| 10 | Offline Detection | 10초 무통신 → OFFLINE |
| 11 | Logging | event_id로 경로 추적 |
| 12 | pytest | 명세 13개 테스트 |
| 13 | Fault Injection | Simulator --fault |
| 14 | Dashboard 4화면 | 폴링 조회 |
| 15 | TROUBLESHOOTING.md | CASE A~D |
| 16 | C# Simulator | HttpClient + retry |
| 17 | README | 실행 방법과 한계 |

구현 원칙: 한 Phase의 입구와 출구를 로그로 증명한다.
거대 시스템이 아니라, 데이터가 이동하는 길을 직접 돌려보는 것이 목표다.
