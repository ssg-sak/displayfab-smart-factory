# DisplayFab 스마트팩토리

OLED/LCD 가상 라인 스마트팩토리 시스템.

설비가 실적과 생존신호를 올리고, 호스트가 지시·조건·인터록으로 라인을 돌리고,
불량이면 멈추고 이력을 추적한다.

설비는 가상이다. PLC 케이블은 없다.

---

## 한 줄

> OLED/LCD 가상 라인을 대상으로 스마트팩토리 시스템을 구현했다.
> 설비가 실적과 생존신호를 올리고, 호스트가 지시·조건·인터록으로 라인을 돌리고,
> 불량이면 멈추고 이력을 추적한다.

---

## 3층

```
설비(가상)
    실적 / 생존신호
        → 호스트 (FastAPI)
        → 검증 · 인터록 · 조건
        → 작업 / 유리 / 알람 / 실적
        → 운전 · 생산
호스트
    켜기 / 끄기 / 조건
        → 설비
```

자세한 설계는 `ARCHITECTURE.md`. 계층 지도는 `ARCHITECTURE_LAYERS.md`. 전체 흐름은 `IMPLEMENTATION_PLAN.md`.

한 이벤트의 경로는 로그의 `request_id` / `event_id`로 따라간다.

---

## 라인

```
올레드: 투입 → 세정 → 증착(1·2호기) → 봉지 → 검사
엘시디: 투입 → 배향막 → 셀 공정 → 검사
```

---

## 데이터

| 대상 | 의미 |
|---|---|
| 설비 | 투입, 세정, 증착×2, 봉지, 배향막, 셀, 검사 |
| 작업 + 카세트 | 작업 묶음 + 캐리어 |
| 유리 | 슬롯 단위 추적 |
| 조건 | 올레드 / 엘시디 공정 조건 |
| 실적 | 공정 이력 |
| 센서 | 그 순간의 측정값 |
| 알람 | 정상에서 벗어난 사건 |
| 명령 | 호스트가 설비·작업에 내린 것 |

설비 상태와 연결 상태는 섞지 않는다.
가동인데 끊김이면 “마지막 보고는 가동, 지금은 데이터가 안 들어온다”.

작업: 대기 → 진행 → 완료. 조건이 틀리면 보류.

---

## 돌리기

터미널 1:

```text
docker compose up -d
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

터미널 2 (설비 생존 + 지시 한 바퀴):

```text
python simulator/python_simulator.py --loop
python simulator/python_simulator.py --run-order
```

브라우저: http://127.0.0.1:8000

C#:

```text
cd csharp_simulator
dotnet run -- --heartbeat --loop
dotnet run -- --run-line
```

---

## 시연 6단

1. 호스트를 켠다. 브라우저에서 운전 화면을 연다
2. **올레드 1장 투입** 을 누르고 **돌리기** → 유리가 라인을 이동한다
3. 세정 **켜기** → 가동, **조건** → 올레드 가가 붙는다
4. 생존을 끊으면 그 설비가 끊기고 실적이 거절된다. 다시 살리면 흐름이 이어진다
5. **검사 불량** → 보류 → 버리기
6. 생산 화면에서 오늘 완료/불량이 맞는지 본다. **엘시디 1장** 도 같은 방식으로 확인한다

설비 카드 아래 작은 줄에 **통신 방식 · 마지막 측정값 · 오늘 정지시간**이 같이 나온다.
생산 화면 5번 칸이 **OEE**(가동률 × 성능 × 품질), 알람 화면이 **측정값 이상 점수**다.
낼 수 없는 숫자는 `-` 로 두고 왜 못 내는지 화면에 적는다.

같은 6단을 화면 대신 API로 한 번에 확인:

```text
cd backend
python scripts/demo_check.py --base http://127.0.0.1:8000
```

---

## 시연 전 초기화

DB는 컨테이너 볼륨에 있다. 파일을 지우는 게 아니다.

```text
docker compose down -v
docker compose up -d
```

다시 뜨면 설비 8대·조건 3개·작업 3건이 새로 들어간다.

---

## 장애

```text
python simulator/python_simulator.py --fault RECIPE_MISMATCH
python simulator/python_simulator.py --fault COMMUNICATION_LOSS
```

끊김, 온도·압력 이탈, 조건 불일치, 없는 작업/유리, 중복 보고, 오래된 시각,
없는 설비, 저장 실패.

---

## 테스트

pytest는 Docker 없이 인메모리 SQLite를 쓴다.

```text
cd backend
python -m pip install -r requirements.txt
python -m pytest -q
```

이벤트 한 건이 상태와 알람까지 바꾸는지 본다.

막히면 화면부터 고치지 않는다. 설비 → HTTP → 검증 → DB → API → 화면 순으로 찾는다.
`TROUBLESHOOTING.md`.

---

## 한계

- 설비는 가상이다. PLC 케이블은 없다
- 조건 숫자는 이 시스템용이다. 현장 스펙이 아니다
- 호스트 DB는 PostgreSQL이다. pytest만 인메모리 SQLite를 쓴다
- 작업 완료는 그 작업의 유리가 검사를 통과했을 때다
- OEE 계획가동시간과 이론 사이클은 이 시스템이 정한 기준이다. 응답에 기준을 같이 낸다
- 이상 점수는 시그마 규칙이다. 학습 모델도 고장 예측도 아니다
- OPC UA / Modbus 어댑터는 자리만 있다. 장비가 없으므로 구현하지 않는다

---

## 일정

월요일까지: `ROADMAP.md`.
시연 6단이 화면에서 닫히면 Day 4가 끝이다.
