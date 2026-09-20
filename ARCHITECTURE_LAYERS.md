# DisplayFab 스마트팩토리 계층 지도

전수조사 결과. 기존 코드를 재사용한다. 실제 PLC / OPC UA / Modbus 장비는 없다.

면접 문장:

> OLED/LCD 가상 라인을 대상으로 스마트팩토리 시스템을 구현했다.
> 설비가 실적과 생존신호를 올리고, 호스트가 지시·조건·인터록으로 라인을 돌리고,
> 불량이면 멈추고 이력을 추적한다.

---

## 현재 데이터 흐름 (코드 기준)

Python과 C#은 **같은 FastAPI로 각각** 붙는다. C#이 Python을 거치지 않는다. (구조 A)

```text
[현장 대신]
simulator/python_simulator.py
csharp_simulator/  (Equipment Client / Edge)

        POST /api/events   JSON + X-Request-Id
        POST /api/commands
                ↓
backend/app/api/events.py
                ↓
services/collector.collect_push
  → SimulatorAdapter.accept_push  → telemetry
  → event_ingestion.ingest_event  → process_event / sensor_reading
  → validation / alarm / downtime
                ↓
PostgreSQL
  equipment.interface_type
  telemetry
  equipment_downtime
  process_event / work_order / alarm
                ↓
GET /api/equipment/interfaces          운전 화면 설비 카드
GET /api/equipment/{id}/interface
GET /api/equipment/{id}/telemetry
GET /api/equipment/{id}/downtime
GET /api/analytics/oee                 생산 화면 5번 칸
GET /api/analytics/anomaly             알람 화면 측정값 이상 점수
GET /api/kpis  /wip  /production  /mes/board  /alarms
                ↓
dashboard/
```

분석 방향은 한 줄이다. 되돌아가지 않는다.

```text
telemetry / downtime  →  oee.py · anomaly.py  →  숫자
                                                  ↓
                                      사람 또는 MES 가 본다
                                                  ↓
                                      POST /api/commands  →  Adapter  →  설비
```

`oee.py`와 `anomaly.py`는 읽기만 한다. 설비를 직접 치지 않는다.

호스트가 설비를 끄는 방향:

```text
운전 화면 켜기/끄기/조건
        ↓
POST /api/commands
        ↓
services/commands.py  →  equipment 상태 / recipe / HOLD
```

C# `--run-line` 은 MES 생산실행이다. 호스트 dispatch를 읽고 PROCESS를 보고한다.

---

## 계층 매핑

| 계층 | 필요한 역할 | 현재 구현 | 상태 | 근거 |
|---|---|---|---|---|
| Field | Sensor / Equipment | `SensorGenerator`, `SensorReading`, 설비 8대 seed | 부분 구현 | `simulator/python_simulator.py`, `csharp_simulator/SensorGenerator.cs`, `models.SensorReading` |
| Control | PLC 역할 | 시뮬레이터가 상태·실적을 만들어 보고 | 부분 구현 | 시뮬레이터가 PLC 자리를 대신함. PLC 프로토콜 없음 |
| Interface | OPC/Modbus/TCP/Simulator | HTTP JSON + SimulatorAdapter. OPC/Modbus는 TODO | 🟡 부분 구현 | `adapters/`, `collector.py`, `POST /api/events` |
| Collection | Data Collector | collect_push → ingest | 구현됨 | `services/collector.py` |
| Equipment Client | C# Client | heartbeat / process / run-line | 구현됨 | `csharp_simulator/` |
| Backend | FastAPI | 라우터 + 서비스 | 구현됨 | `backend/app/main.py` |
| Data | DB / Repository | SQLAlchemy + telemetry/downtime. Repository 계층 없음 | 부분 구현 | `models.py`, `database.py`, 서비스가 Session을 직접 씀 |
| MES | 생산관리 | 지시·실행·실적·품질·추적 | 구현됨 | `work_orders.py`, `line_runner.py`, `mes.py`, `history.py` |
| Monitoring | Dashboard/HMI | 운전 라인, KPI, SSE | 구현됨 | `dashboard/`, `GET /api/kpis`, `/stream` |
| Quality | 품질관리 | INSPECT PASS/FAIL/SCRAP, 수율 | 구현됨 | `Panel.status`, `kpis.yield_pct`, `test_quality.py` |
| Alarm | Alarm/Event | 코드별 알람 + event_log | 구현됨 | `alarm_service.py`, `offline.py`, `GET /api/alarms` |
| Analytics | KPI/OEE | KPI·수율 + OEE 세 요소 | 구현됨 | `kpis.py`, `services/oee.py`, `GET /api/analytics/oee` |
| AI | 이상탐지/예측 | 시그마 기반 이상 점수. 학습·예측은 없음 | 부분 구현 | `services/anomaly.py`, `GET /api/analytics/anomaly` |
| Feedback | 작업지시/제어반영 | 명령 → DB. 시뮬레이터가 명령을 폴링하지는 않음 | 부분 구현 | `commands.py`. 분석이 PLC를 직접 치지 않음 |

상태 네 가지: 구현됨 / 부분 구현 / 구조만 존재 / 없음.

---

## 모델 대응

| 개념 | 기존 | 추가 여부 |
|---|---|---|
| Equipment | `equipment` | 그대로 |
| ProductionLine | `domain/rules.py` OLED_ROUTE / LCD_ROUTE | 테이블 불필요 |
| Telemetry | `telemetry` + PROCESS의 `sensor_reading` | 그대로 사용 |
| EquipmentStatus | IDLE/RUN/STOP/ERROR/MAINTENANCE + ONLINE/OFFLINE | 그대로 |
| Downtime | `equipment_downtime` | 신규. OEE Availability 재료 |
| ProductionEvent | `process_event` | 그대로 |
| Alarm | `alarm` | 그대로 |
| WorkOrder | `work_order` | 그대로 |
| ProductionResult | `production.py` closeout, Panel COMPLETE/FAIL | 그대로 |
| QualityResult | `inspect_result`, Panel FAIL/SCRAP | 그대로 |

---

## OEE 데이터

```text
Availability  (계획가동시간 - equipment_downtime) / 계획가동시간
Performance   domain/rules.IDEAL_CYCLE_SEC 합 / 가동시간
Quality       COMPLETE / (COMPLETE+FAIL+SCRAP), 유리 단위

계획가동시간 기준: DISPLAYFAB_OEE_PLANNED_MINUTES, 0이면 오늘 첫 보고부터 지금까지
              응답의 planned_basis 에 어느 기준인지 같이 나온다
못 내는 것:    실적 없으면 performance=null, 판정 없으면 quality=null
              라인이 안 열렸으면 availability=null. 하나라도 null이면 oee=null
가짜 가동시간으로 OEE를 채우지 않는다. 이유는 missing 에 문장으로 남는다.
```

---

## C# 역할

`csharp_simulator` = **Equipment / Edge Client**.
HTTP로 호스트에 생존신호·실적을 올리고, `--run-line`으로 생산실행을 따른다.
`csharp_lessons` = 언어 연습. 라인과 무관.

Python 시뮬레이터와 동일 프로토콜: HEARTBEAT, PROCESS, 온도/압력, fault, run-order/run-line.
서로 경유하지 않고 둘 다 FastAPI로 간다.

---

## 목표 구조 (현재 코드 보존)

```text
FIELD          Simulator / 가상 Sensor
CONTROL/EDGE   C# · Python Equipment Client  (PLC 개념, 프로토콜 아님)
COMMUNICATION  HTTP/JSON 현재
               EquipmentAdapter → Simulator | OPC UA(TODO) | Modbus(TODO)
BACKEND        FastAPI · services · PostgreSQL
DATA           Equipment Telemetry Production Quality Alarm
MES            Work Order · run-line/run-order · Quality · Traceability
MONITORING     dashboard · /kpis · /wip · alarms
ANALYTICS      KPI 있음 · OEE/이상탐지는 자리만
FEEDBACK       Operator/MES → /api/commands → (미래) Adapter
               Analytics가 설비를 직접 치지 않음
```

---

## Gap

[이미 구현됨]
1. 이벤트 수집·검증·저장
2. C# / Python 설비 클라이언트
3. 지시·라인 실행·재공·오늘 실적
4. 알람·끊김 감지·품질·추적
5. 운전/생산 화면

6. OEE 세 요소 + 이상 점수 (운전·생산·알람 화면에 붙음)

[부분 구현]
1. telemetry는 보고 시점마다 한 점. 설비 상시 스트림은 아님
2. 호스트 명령은 Adapter를 거쳐 DB에 남고, 설비가 명령을 구독하지 않음
3. Repository 없이 서비스가 DB를 직접 씀
4. 계획가동시간은 현장 교대표가 아니라 이 시스템이 정한 기준
5. 이상탐지는 시그마 규칙이다. 학습도 예측도 없음

[구조만 추가]
1. EquipmentAdapter (시뮬레이터만 실체)
2. OPC UA / Modbus TODO

[현재 단계에서 불필요]
1. K8s
2. Kafka
3. 실제 PLC 스택
4. AI 학습 / 수명 예측
5. 새 대시보드 프레임워크

[향후 실제 장비 연결 시]
1. OPCUAAdapter / ModbusAdapter 실체
2. Collector가 구독/폴링 후 같은 ingest 경로 호출 (push → pull)
3. 현장 교대표를 계획가동시간으로 연결

---

## TODO 우선순위

```text
P0  이 지도와 Adapter 계약을 유지. 기존 API 삭제 금지
    시연 전 `python scripts/demo_check.py` 로 6단 + 인터페이스 + OEE 를 한 번에 확인
    공개 시연은 DISPLAYFAB_DEMO_AUTOPILOT=1 일 때만 서버가 설비 클라이언트를 대신한다
P1  (완료) 운전 화면 통신방식 / 마지막 측정값 / 정지시간
    (완료) 돌리기 중 생존신호 유지 — 시뮬레이터가 5초마다 라인 전체 HEARTBEAT
P2  실제 장비가 생겼을 때만 OPCUAAdapter / ModbusAdapter 실체. 시뮬레이터는 옆에 유지
    장비 없이 미리 구현하지 않는다. 지금은 NotImplementedError 가 정답이다
P3  (완료) OEE · 이상 점수. Analytics → 숫자만. 알람·명령은 사람/MES
    남은 것: 현장 교대표, 설비별 정상 구간 마스터. 데이터가 생기면 붙인다
```
