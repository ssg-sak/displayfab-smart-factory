# C# 처음 배우기 — DisplayFab Ops Lab

Python Simulator는 이미 있다.
C#은 **같은 일을 다른 언어로 다시 보내는 프로그램**이다.

PLC가 아니다. FastAPI에 JSON을 POST 하는 콘솔 앱이다.

```
C# 프로그램  =  가상 OLED Evap 설비 (PROC-01)
       │
       │  HTTP POST JSON
       ▼
FastAPI /api/events
```

지금 PC에 `dotnet`이 없으면 0부터 한다.

---

## 0. SDK 설치

PowerShell:

```text
winget install Microsoft.DotNet.SDK.8 --accept-package-agreements --accept-source-agreements
```

설치 후 **터미널을 닫았다가 다시 연 다음**:

```text
dotnet --version
```

`8.` 로 시작하면 된다.

에디터: Cursor에서 `.cs` 파일을 열면 된다.

---

## Python과 C#이 다른 점 (이 Lab에서 필요한 것만)

| Python | C# |
|---|---|
| 들여쓰기가 블록 | `{ }` 가 블록 |
| 타입을 안 적어도 됨 | 변수에 타입을 적는다 `string`, `int`, `double` |
| `dict` 로 JSON을 만듦 | `class` 의 필드가 JSON이 됨 |
| `def send():` | `public async Task<HttpResponseMessage> PostAsync()` |
| `httpx.Client()` | `HttpClient` |
| `None` | `null` |
| `self` | `this` (보통 생략) |
| `print(x)` | `Console.WriteLine(x)` |

문법은 까다로워 보이지만, 이 프로젝트에서 하는 일은 Python과 같다.

1. 센서값 만들기
2. 이벤트 객체 만들기
3. JSON으로 바꿔서 POST
4. 실패하면 한두 번 재시도

---

## 실습 순서

1. `csharp_lessons/01_hello` — 콘솔에 글자 출력
2. `csharp_lessons/02_class` — 설비 이벤트 class
3. `csharp_lessons/03_if_loop` — if / for, 설비 상태 분기
4. `csharp_simulator` — 진짜 FastAPI로 POST

한 단계가 되면 다음으로 간다.
처음부터 Simulator를 읽지 마라. `01_hello`부터 실행한다.

---

## Lesson 1 — Hello

```text
cd "d:\display ops practice\csharp_lessons\01_hello"
dotnet run
```

기대 출력:

```text
DisplayFab C# lesson 1
PROC-01 is IDLE
```

여기서 볼 것:

- `Main` : 프로그램이 시작되는 함수. Python의 `if __name__ == "__main__"` 자리.
- `string equipmentId = "PROC-01";` : 문자열 변수.
- `$"..."` : Python f-string 과 비슷하다.

---

## Lesson 2 — class

```text
cd "d:\display ops practice\csharp_lessons\02_class"
dotnet run
```

Python의

```python
event = {
    "equipment_id": "PROC-01",
    "lot_id": "LOT-20260918-001",
}
```

를 C#에서는 이렇게 적는다.

```csharp
var evt = new EquipmentEvent();
evt.EquipmentId = "PROC-01";
evt.LotId = "LOT-20260918-001";
```

`class` 는 “이 모양의 데이터를 담는 상자”다.
JSON 키 이름은 `[JsonPropertyName("equipment_id")]` 로 Python API와 맞춘다.

---

## Lesson 3 — if / for

```text
cd "d:\display ops practice\csharp_lessons\03_if_loop"
dotnet run
```

기대 출력:

```text
DisplayFab C# lesson 3
PROC-01 status=IDLE mode=heartbeat
PROCESS ok — IDLE/RUN 은 받는다
heartbeat 1 PROC-01
heartbeat 2 PROC-01
heartbeat 3 PROC-01
```

Python과 짝:

| Python | C# |
|---|---|
| `if status == "STOP":` | `if (status == "STOP") { }` |
| `elif ...:` | `else if (...) { }` |
| `for i in range(1, 4):` | `for (int i = 1; i <= 3; i++) { }` |

`status` 를 `"STOP"` 으로 바꿔 다시 실행하면 거절 한 줄만 나오고 heartbeat는 그대로다. `mode` 를 `"process"` 로 바꾸면 PROCESS 한 줄이 나온다.

---

## Lesson 4 — 실제 Simulator

FastAPI가 켜져 있어야 한다.

터미널 1:

```text
cd "d:\display ops practice\backend"
python -m uvicorn app.main:app --reload --port 8000
```

터미널 2:

```text
cd "d:\display ops practice\csharp_simulator"
dotnet run
```

한 건의 HEARTBEAT를 보낸다. LOT가 없어도 된다. PROC-01이 ONLINE이 되면 성공이다.

설비가 살아 있는 신호를 계속 보내려면:

```text
dotnet run -- --heartbeat --loop
```

3초마다 POST. Dashboard에서 PROC-01 Conn이 ONLINE, Last seen이 갱신되면 된 것이다.
Ctrl+C로 멈추고 10초 기다리면 OFFLINE + COMMUNICATION_LOSS.
다시 `--loop`를 켜면 reconnect — ONLINE으로 돌아오고 통신 Alarm은 풀린다.

호스트가 꺼져 있어도 루프는 죽지 않는다. FastAPI를 다시 켜면 `reconnected`가 찍힌다.

침묵만 재현 (프로세스는 살리고 전송만 끊기):

```text
dotnet run -- --heartbeat --loop --drop-after 3
```

지시 LOT를 호스트가 준 다음 공정만 따라 끝까지 보고하려면:

```text
dotnet run -- --run-line
dotnet run -- --run-line WO-...
```

Ops Console에서 먼저 투입한다. `--run-line`은 GET `/api/lots/{lot}/dispatch` 로 next_step을 받고 PROCESS를 보낸다. heartbeat와 섞지 않는다.

PROCESS(EVAP) 보내기 (그 전에 Python으로 LOAD를 한 장이라도 넣는 것이 안전하다):

```text
python simulator/python_simulator.py
dotnet run -- --process
```

Recipe mismatch:

```text
dotnet run -- --fault RECIPE_MISMATCH
```

`--` 가 두 번인 이유: 앞의 `--` 는 `dotnet run` 에게
“여기서부터는 내 프로그램 인자”라고 알려주는 표시다.

---

## Simulator 파일 역할

| 파일 | 하는 일 | Python 짝 |
|---|---|---|
| `Program.cs` | 시작, 인자 파싱, 실행 | `if __name__ == "__main__"` |
| `EquipmentEvent.cs` | JSON으로 나갈 데이터 모양 | event dict |
| `SensorGenerator.cs` | 온도/압력 난수 | `SensorGenerator` |
| `EquipmentSimulator.cs` | HTTP GET dispatch + POST + retry | `EquipmentSimulator.send` |

코드를 읽을 때 이 순서로 본다.

`Program.cs` → `SensorGenerator.cs` → `EquipmentEvent.cs` → `EquipmentSimulator.cs`

---

## 지금 몰라도 되는 것

- LINQ
- interface / inheritance
- ASP.NET (서버). 우리는 **클라이언트**만 쓴다.
- WPF / WinForms
- `async` 의 내부 구현. “기다렸다가 응답 온다” 정도면 된다.

`await http.PostAsJsonAsync(...)` 는
Python `client.post(...)` 가 끝날 때까지 기다리는 것과 같다.

---

## 막히면

1. `dotnet --version` 이 되는가
2. FastAPI `http://127.0.0.1:8000/api/health` 가 되는가
3. C# 터미널에 `HTTP 200` 이 찍히는가
4. Dashboard Equipment 의 PROC-01 Last Seen 이 바뀌는가
