# TROUBLESHOOTING

DisplayFab Ops Lab 장애 조사 순서.

화면만 보지 않는다. 데이터가 이동하는 길을 따라간다.

```
Simulator → HTTP request → Network → FastAPI → Validation → DB → 조회 API → UI
```

로그 키: `request_id`, `event_id`

---

## CASE A — PROC-01이 OFFLINE이다

의미: 마지막 유효 수신 시각(`last_seen_at`)이 `COMMUNICATION_TIMEOUT_SEC`(기본 10초)를 넘었다.
Equipment status가 RUN이어도 Connection은 OFFLINE일 수 있다.

확인 순서:

1. **Simulator**
   - Python/C# Simulator가 살아 있는가
   - `--fault COMMUNICATION_LOSS`로 일부러 안 보내고 있지는 않은가
2. **HTTP request**
   - `POST /api/events`가 실제로 나가는가
   - 터미널에 `HTTP error` / timeout이 있는가
3. **Network**
   - API URL이 `http://127.0.0.1:8000/api/events`인가
   - 서버 포트가 8000인가
4. **FastAPI**
   - uvicorn이 떠 있는가
   - `GET /api/health`가 ok인가
5. **Validation**
   - 이벤트는 오는데 reject만 반복되면 last_seen은 갱신된다
   - 아예 요청이 없으면 last_seen이 멈춘다
6. **DB**
   - `equipment.last_seen_at`, `connection_status`
7. **조회 API**
   - `GET /api/equipment/PROC-01`
8. **UI**
   - Equipment Monitor의 Connection 컬럼
   - 폴링이 멈춰 있으면 서버는 ONLINE인데 화면만 옛날일 수 있다

한 줄: OFFLINE은 센서값이 이상한 게 아니라, 데이터가 안 들어온 상태다.

C# heartbeat를 쓰는 경우:

```text
cd csharp_simulator
dotnet run -- --heartbeat --loop
```

PROC-01 Last seen이 3초마다 바뀌면 산 것이다. 멈추거나 `--drop-after`면 10초 뒤 OFFLINE + COMMUNICATION_LOSS.

---

## CASE B — LOT가 HOLD 되었다

의미: 시스템이 이 LOT의 진행을 막았다. 이 Lab에서 주원인은 RECIPE_MISMATCH.

확인:

1. **Alarm 조회**
   - `GET /api/alarms?lot_id=LOT-20260918-001`
   - RECIPE_MISMATCH / TEMPERATURE / PRESSURE 중 무엇인가
2. **Recipe 비교**
   - `GET /api/lots/{lot_id}` 의 `expected_recipe_id`
   - 최근 `GET /api/lots/{lot_id}/history` 의 `recipe_id`
3. **Sensor 범위**
   - 온도/압력 Alarm이 같이 떴는가
   - 범위는 seed Recipe (학습용) 기준이다
4. **최근 Event**
   - 이력이 저장됐는가, reject만 됐는가
5. **설비 상태**
   - PROC-01이 어떤 Recipe를 current_recipe로 들고 있는가

HOLD여도 mismatch 이벤트는 이력에 남긴다.
“잘못된 일을 숨기지 않고, 더 진행만 막는다.”

---

## CASE C — DB는 공정 완료인데 Dashboard는 PROCESSING이다

의미: 저장과 화면이 다른 계층에 있다.

확인:

1. **DB**
   - `lot.status`, `panel.status`, `process_event` 건수
2. **backend query**
   - `GET /api/lots/{lot_id}` 가 DB와 같은가
   - LOT COMPLETE 조건: 그 LOT의 **모든 Panel**이 INSPECT를 끝냈는가
   - 한 Panel만 끝나도 LOT는 PROCESSING일 수 있다 (의도된 모델)
3. **API response**
   - 브라우저 네트워크 탭에서 `/api/lots` JSON
4. **frontend state**
   - 2초 폴링이 실패하고 있지 않은가
   - 캐시된 HTML을 보고 있지 않은가

한 줄: DB → API → 화면 순으로 깨진 층을 찾는다. 화면만 고치면 원인에 도달하지 못한다.

---

## CASE D — Panel 이력이 하나 빠졌다

의미: 설비가 보냈다고 생각한 이벤트가 저장되지 않았다.

확인:

1. **Simulator event**
   - 해당 panel_id, process_step, timestamp를 보냈는가
2. **API access log**
   - `EVENT_RECEIVED` 로그가 있는가
   - `request_id` / `event_id`
3. **validation rejection**
   - UNKNOWN_EQUIPMENT, INVALID_LOT, INVALID_PANEL
   - DUPLICATE_EVENT, STALE_TIMESTAMP
   - reject면 process_event는 없고 Alarm만 있다
4. **DB**
   - `SELECT * FROM process_event WHERE panel_id='PNL-00001' ORDER BY event_timestamp`
5. **query**
   - `GET /api/panels/PNL-00001/history`
   - API가 비었으면 UI도 빈다

한 줄: 이력 누락은 대부분 전송 실패가 아니라 validation reject다. Alarm 테이블을 같이 본다.

Replay가 전부 reject면 timestamp를 지금으로 바꿨는지 먼저 본다 (`refresh_timestamps`).
옛 이력을 그대로 넣으면 STALE_TIMESTAMP다. 같은 Panel에 다시 넣으면 순서/중복이다.

---

## CASE E — 서버가 안 뜬다 / health db 가 아니다

호스트 DB는 PostgreSQL이다. `displayfab.db` 파일은 쓰지 않는다.

1. `docker compose up -d`
2. `GET /api/health` 의 `db` 가 `ok` 인가
3. 연결 문자열은 `DISPLAYFAB_DATABASE_URL` (`postgresql+psycopg://...`)
4. 포트 8000이나 5435를 다른 프로그램이 이미 쓰고 있지 않은가
   - `docker ps` 로 확인. 겹치면 `--port 8010` 처럼 옮긴다
5. 6단이 실제로 닫히는지는 `python scripts/demo_check.py --base http://127.0.0.1:8000`
