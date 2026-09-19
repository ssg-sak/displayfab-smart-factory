"""시연 6단을 실제 서버에 그대로 걸어 본다.

운전 화면이 누르는 API만 쓴다. 통과하면 화면에서도 닫힌다.

  python scripts/demo_check.py --base http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "OK  " if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" : {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


def now_iso(offset_sec: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_sec)).isoformat()


def heartbeat(client: httpx.Client, equipment_id: str) -> dict:
    res = client.post(
        "/api/events",
        json={
            "equipment_id": equipment_id,
            "event_type": "HEARTBEAT",
            "equipment_status": "IDLE",
            "timestamp": now_iso(),
        },
        headers={"X-Request-Id": str(uuid.uuid4())},
    )
    return res.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base, timeout=20.0)

    health = client.get("/api/health").json()
    check("호스트 살아 있음", health.get("db") == "ok", f"db={health.get('db')}")

    # 1. 지시 넣고 돌리기
    order = client.post("/api/work-orders", json={"product_type": "OLED", "qty": 1}).json()
    check("올레드 1장 지시", bool(order.get("lot_id")), order.get("id", ""))
    run = client.post(f"/api/lab/run-order/{order['id']}").json()
    steps = run.get("results", run if isinstance(run, list) else [])
    accepted = [s for s in steps if s.get("accepted")]
    check("돌리기로 라인 통과", len(accepted) >= 4, f"수용 {len(accepted)}건")

    board = client.get("/api/production").json()
    check("오늘 완료 1장", board["oled"]["complete"] >= 1, f"complete={board['oled']['complete']}")

    # 2. 켜기 / 조건
    stop = client.post("/api/commands", json={"command_type": "STOP", "equipment_id": "CLEAN-01"}).json()
    check("세정 끄기", stop["status"] == "ACCEPTED", stop["message"])
    check("끄기가 어댑터를 지남", stop.get("interface_type") == "simulator", str(stop.get("delivered_at")))
    start = client.post("/api/commands", json={"command_type": "START", "equipment_id": "CLEAN-01"}).json()
    check("세정 켜기", start["status"] == "ACCEPTED", start["message"])
    recipe = client.post(
        "/api/commands",
        json={"command_type": "SELECT_RECIPE", "equipment_id": "CLEAN-01", "recipe_id": "RCP-OLED-A01"},
    ).json()
    check("조건 걸기", recipe["status"] == "ACCEPTED", recipe["message"])

    down = client.get("/api/equipment/CLEAN-01/downtime").json()
    closed = [row for row in down if row["reason"] == "STOP" and row["ended_at"]]
    check("정지 구간이 닫힘", bool(closed), f"{len(closed)}건")

    # 3. 생존 끊기 → 실적 거절
    order2 = client.post("/api/work-orders", json={"product_type": "OLED", "qty": 1}).json()
    glass = order2["panel_ids"][0]
    heartbeat(client, "PROC-01")
    print("      ... 통신 끊김 대기 (12초)")
    time.sleep(12)
    eq = client.get("/api/equipment/PROC-01").json()
    check("끊긴 설비", eq["connection_status"] == "OFFLINE", eq["connection_status"])
    loss = client.get("/api/equipment/PROC-01/downtime").json()
    check(
        "끊김이 정지시간으로 남음",
        any(r["reason"] == "COMMUNICATION_LOSS" and not r["ended_at"] for r in loss),
        f"{len(loss)}건",
    )
    rejected = client.post(
        "/api/events",
        json={
            "equipment_id": "PROC-01",
            "event_type": "PROCESS",
            "lot_id": order2["lot_id"],
            "panel_id": glass,
            "process_step": "EVAP",
            "recipe_id": "RCP-OLED-A01",
            "equipment_status": "RUN",
            "chamber_temperature": 118.0,
            "vacuum_pressure": 0.004,
            "timestamp": now_iso(),
        },
    ).json()
    check("끊긴 설비 실적 거절", rejected["accepted"] is False, str(rejected.get("reason")))

    # 4. 다시 살리기
    hb = heartbeat(client, "PROC-01")
    check("다시 생존", hb.get("accepted") is True)
    eq = client.get("/api/equipment/PROC-01").json()
    check("연결 회복", eq["connection_status"] == "ONLINE", eq["connection_status"])
    loss = client.get("/api/equipment/PROC-01/downtime").json()
    check(
        "정지시간 집계됨",
        any(r["reason"] == "COMMUNICATION_LOSS" and r["duration_sec"] for r in loss),
        "",
    )
    tel = client.get("/api/equipment/PROC-01/telemetry").json()
    check("측정값이 쌓임", len(tel) >= 1, f"{len(tel)}건")

    # 5. 검사 불량 → 보류 → 버리기
    fail = client.post("/api/lab/scenarios/oled_inspect_fail/run").json()
    check("검사 불량 시연", bool(fail), "")
    today = client.get("/api/production").json()
    check("보류가 화면에 뜸", bool(today["hold_lots"]), ", ".join(today["hold_lots"][:3]))
    check("왜 멈췄는지 보임", "보류" in today["blocked"], today["blocked"][:40])

    hold_lot = today["hold_lots"][0]
    slots = client.get(f"/api/lots/{hold_lot}/slots").json()
    bad = next((s for s in slots["slots"] if s["status"] in ("FAIL", "HOLD")), None)
    if bad:
        scrap = client.post(
            "/api/commands",
            json={"command_type": "SCRAP_PANEL", "panel_id": bad["panel_id"]},
        ).json()
        check("불량 유리 버리기", scrap["status"] == "ACCEPTED", scrap["message"])

    # 6. 생산 화면 마감
    mes = client.get("/api/mes/board").json()
    check("생산 화면 지시 있음", len(mes["orders"]) >= 2, f"{len(mes['orders'])}건")
    wip = client.get("/api/wip").json()
    check("재공 집계", wip["complete"] >= 1, f"complete={wip['complete']}")
    kpi = client.get("/api/kpis").json()
    check("수율 계산", kpi["yield_pct"] is not None, f"yield={kpi['yield_pct']}")
    close = client.get("/api/production").json()["closeout"]
    check("마감 한 줄", bool(close and close["line"]), (close or {}).get("line", "")[:40])

    # 7. 운전 화면이 읽는 인터페이스 요약
    ifaces = client.get("/api/equipment/interfaces").json()
    check("설비 통신 요약 8대", len(ifaces) == 8, f"{len(ifaces)}대")
    proc_if = next((r for r in ifaces if r["equipment_id"] == "PROC-01"), {})
    check("통신 방식 노출", proc_if.get("transport") == "HTTP/JSON", str(proc_if.get("interface_type")))
    check("마지막 측정값 노출", proc_if.get("recorded_at") is not None, str(proc_if.get("chamber_temperature")))
    check("정지시간 노출", proc_if.get("downtime_sec_today", 0) > 0, f"{proc_if.get('downtime_sec_today')}초")

    # 8. OEE / 이상 점수
    oee = client.get("/api/analytics/oee").json()
    check("OEE 가동률", oee["availability"] is not None, f"A={oee['availability']}")
    check("OEE 품질", oee["quality"] is not None, f"Q={oee['quality']}")
    check("OEE 한 숫자", oee["oee"] is not None, f"OEE={oee['oee']}")
    check("OEE 기준 명시", "현장 스펙이 아니다" in oee["note"], oee["planned_basis"])
    evap = next((r for r in oee["equipment"] if r["equipment_id"] == "PROC-01"), {})
    check("증착 이론 사이클 반영", evap.get("ideal_runtime_sec", 0) > 0, f"{evap.get('ideal_runtime_sec')}초")

    anomaly = client.get("/api/analytics/anomaly").json()
    check("이상 점수 응답", bool(anomaly.get("equipment")), f"{len(anomaly.get('equipment', []))}대")
    check("학습 모델 아님을 명시", "학습 모델이 아니고" in anomaly["note"], anomaly["method"][:30])
    alarms_before = len(client.get("/api/alarms").json())
    client.get("/api/analytics/anomaly")
    check(
        "분석이 설비를 치지 않음",
        len(client.get("/api/alarms").json()) == alarms_before,
        f"알람 {alarms_before}건 유지",
    )

    # 화면 자체
    for page in ["/", "/mes.html", "/alarms.html", "/lots.html", "/traceability.html"]:
        res = client.get(page)
        check(f"화면 {page}", res.status_code == 200, str(res.status_code))

    client.close()
    print()
    if FAILURES:
        print(f"실패 {len(FAILURES)}건: " + ", ".join(FAILURES))
        return 1
    print("시연 6단 전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
