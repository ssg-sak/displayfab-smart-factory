"""가상 설비 시뮬레이터.

실제 PLC가 아니다. FastAPI로 JSON 이벤트를 보내는 학습용 클라이언트다.

사용 예:
  python simulator/python_simulator.py
  python simulator/python_simulator.py --fault RECIPE_MISMATCH
  python simulator/python_simulator.py --fault COMMUNICATION_LOSS
  python simulator/python_simulator.py --run-order

"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

API_URL = "http://127.0.0.1:8000/api/events"

RECIPES = {
    "RCP-OLED-A01": {"temp": (112.0, 128.0), "pressure": (0.0032, 0.0075)},
    "RCP-OLED-B01": {"temp": (142.0, 158.0), "pressure": (0.0022, 0.0055)},
    "RCP-LCD-C01": {"temp": (82.0, 93.0), "pressure": (0.85, 1.15)},
}

OLED_FLOW = [
    ("LOAD-01", "LOAD", None),
    ("CLEAN-01", "CLEAN", 18.0),
    ("PROC-01", "EVAP", 46.0),
    ("ENC-01", "ENCAP", 30.0),
    ("INSPECT-01", "INSPECT", 12.0),
]

LCD_FLOW = [
    ("LOAD-01", "LOAD", None),
    ("PI-01", "PI", 22.0),
    ("LCD-01", "LCD_CELL", 40.0),
    ("INSPECT-01", "INSPECT", 12.0),
]


class SensorGenerator:
    def __init__(self, recipe_id: str) -> None:
        self.recipe_id = recipe_id
        self.spec = RECIPES[recipe_id]

    def reading(self, fault: Optional[str]) -> tuple[float, float]:
        t_lo, t_hi = self.spec["temp"]
        p_lo, p_hi = self.spec["pressure"]
        temp = random.uniform(t_lo, t_hi)
        pressure = random.uniform(p_lo, p_hi)
        if fault == "TEMPERATURE_OUT_OF_RANGE":
            temp = 210.0
        if fault == "PRESSURE_OUT_OF_RANGE":
            pressure = 0.9
        return round(temp, 2), round(pressure, 5)


class EquipmentSimulator:
    def __init__(self, api_url: str, timeout_sec: float = 5.0) -> None:
        self.api_url = api_url
        self.timeout_sec = timeout_sec
        self.client = httpx.Client(timeout=timeout_sec)

    def send(self, event: dict, force_db_failure: bool = False) -> httpx.Response:
        url = self.api_url
        if force_db_failure:
            url = f"{self.api_url}?force_db_failure=true"
        headers = {"X-Request-Id": str(uuid.uuid4())}
        try:
            return self.client.post(url, json=event, headers=headers)
        except httpx.RequestError as exc:
            print(f"HTTP error: {exc}", file=sys.stderr)
            raise

    def close(self) -> None:
        self.client.close()


def build_event(
    equipment_id: str,
    process_step: str,
    lot_id: str,
    panel_id: str,
    recipe_id: str,
    temp: float,
    pressure: float,
    cycle_time: Optional[float],
    inspect_result: Optional[str] = None,
    timestamp: Optional[str] = None,
    event_type: str = "PROCESS",
) -> dict:
    body = {
        "equipment_id": equipment_id,
        "event_type": event_type,
        "lot_id": lot_id,
        "panel_id": panel_id,
        "process_step": process_step,
        "recipe_id": recipe_id,
        "equipment_status": "IDLE" if event_type == "HEARTBEAT" else "RUN",
        "chamber_temperature": temp,
        "vacuum_pressure": pressure,
        "cycle_time_sec": cycle_time,
        "alarm_code": None,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "inspect_result": inspect_result,
    }
    if event_type == "HEARTBEAT":
        body["lot_id"] = None
        body["panel_id"] = None
        body["process_step"] = None
    return body


def host_prep(sim: EquipmentSimulator, api_url: str, recipe_id: str) -> None:
    base = api_url.replace("/api/events", "")
    for eq_id in ["LOAD-01", "CLEAN-01", "PROC-01", "PROC-02", "ENC-01", "PI-01", "LCD-01", "INSPECT-01"]:
        sim.client.post(f"{base}/api/commands", json={"command_type": "START", "equipment_id": eq_id})
    recipe_eq = ["PI-01", "LCD-01"] if recipe_id.startswith("RCP-LCD") else ["CLEAN-01", "PROC-01", "PROC-02", "ENC-01"]
    for eq_id in recipe_eq:
        sim.client.post(
            f"{base}/api/commands",
            json={"command_type": "SELECT_RECIPE", "equipment_id": eq_id, "recipe_id": recipe_id},
        )


LINE_EQUIPMENT = ["LOAD-01", "CLEAN-01", "PROC-01", "PROC-02", "ENC-01", "PI-01", "LCD-01", "INSPECT-01"]

HEARTBEAT_EVERY_SEC = 5.0


class Heartbeats:
    """라인을 돌리는 동안에도 설비는 살아 있다고 계속 알린다.

    실제 설비는 공정 중에도 생존신호를 보낸다. 여기서도 같은 주기로 보낸다.
    보고가 멈추면 호스트가 통신 끊김으로 보고 실적을 거절한다.
    """

    def __init__(self, sim: "EquipmentSimulator") -> None:
        self.sim = sim
        self.last = 0.0

    def beat(self, force: bool = False) -> None:
        if not force and time.monotonic() - self.last < HEARTBEAT_EVERY_SEC:
            return
        self.last = time.monotonic()
        for eq_id in LINE_EQUIPMENT:
            event = build_event(eq_id, None, None, None, "RCP-OLED-A01", None, None, None, event_type="HEARTBEAT")
            # 호스트가 켠 설비다. 생존신호로 대기 상태로 되돌리지 않는다.
            event["equipment_status"] = "RUN"
            sim_send_quiet(self.sim, event)


def sim_send_quiet(sim: "EquipmentSimulator", event: dict) -> None:
    try:
        sim.send(event)
    except Exception as exc:  # 생존신호는 실패해도 라인을 멈추지 않는다
        print(f"heartbeat failed: {exc}")


def run_normal(sim: EquipmentSimulator, lot_id: str, panel_id: str, recipe_id: str) -> None:
    sensors = SensorGenerator(recipe_id)
    flow = LCD_FLOW if recipe_id.startswith("RCP-LCD") else OLED_FLOW
    for equipment_id, step, cycle in flow:
        temp, pressure = sensors.reading(None)
        inspect = "PASS" if step == "INSPECT" else None
        event = build_event(
            equipment_id, step, lot_id, panel_id, recipe_id, temp, pressure, cycle, inspect
        )
        print(json.dumps({"send": event["equipment_id"], "step": step, "panel": panel_id, "product": recipe_id}))
        res = sim.send(event)
        print(res.status_code, res.text)
        time.sleep(0.4)


def run_fault(sim: EquipmentSimulator, fault: str, lot_id: str, panel_id: str, recipe_id: str) -> None:
    sensors = SensorGenerator(recipe_id if recipe_id in RECIPES else "RCP-OLED-A01")

    if fault == "COMMUNICATION_LOSS":
        print("COMMUNICATION_LOSS: 이벤트를 보내지 않습니다. 10초 후 OFFLINE을 확인하세요.")
        return

    if fault == "HEARTBEAT":
        event = build_event("PROC-01", "EVAP", lot_id, panel_id, recipe_id, 118.0, 0.004, None, event_type="HEARTBEAT")
        print(sim.send(event).text)
        return

    if fault == "INVALID_LOT":
        event = build_event("PROC-01", "EVAP", "LOT-NOPE", panel_id, recipe_id, 118.0, 0.004, 47.0)
        print(sim.send(event).text)
        return

    if fault == "INVALID_PANEL":
        event = build_event("PROC-01", "EVAP", "LOT-20260918-002", "PNL-00001", recipe_id, 118.0, 0.004, 47.0)
        print(sim.send(event).text)
        return

    if fault == "UNKNOWN_EQUIPMENT":
        event = build_event("EQ-UNKNOWN", "EVAP", lot_id, panel_id, recipe_id, 118.0, 0.004, 47.0)
        print(sim.send(event).text)
        return

    if fault == "STALE_TIMESTAMP":
        old = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        event = build_event("PROC-01", "EVAP", lot_id, panel_id, recipe_id, 118.0, 0.004, 47.0, timestamp=old)
        print(sim.send(event).text)
        return

    if fault == "PRODUCT_ROUTE":
        event = build_event("LOAD-01", "LOAD", "LOT-20260918-003", "PNL-00011", "RCP-LCD-C01", 88.0, 1.0, 10.0)
        print("lcd load", sim.send(event).text)
        event = build_event("PROC-01", "EVAP", "LOT-20260918-003", "PNL-00011", "RCP-LCD-C01", 88.0, 1.0, 47.0)
        print("oled evap blocked", sim.send(event).text)
        return

    if fault == "SKIP_STEP":
        event = build_event("LOAD-01", "LOAD", lot_id, panel_id, recipe_id, 118.0, 0.004, 10.0)
        print("load", sim.send(event).text)
        event = build_event("INSPECT-01", "INSPECT", lot_id, panel_id, recipe_id, 118.0, 0.004, 12.0, inspect_result="PASS")
        print("skip encap", sim.send(event).text)
        return

    load = build_event("LOAD-01", "LOAD", lot_id, panel_id, recipe_id, *sensors.reading(None), 10.0)
    print("load", sim.send(load).text)

    if fault == "DUPLICATE_EVENT":
        event = build_event("PROC-01", "EVAP", lot_id, panel_id, recipe_id, 118.0, 0.004, 47.0)
        print("first", sim.send(event).text)
        print("second", sim.send(event).text)
        return

    if fault == "DB_WRITE_FAILURE":
        event = build_event("PROC-01", "EVAP", lot_id, panel_id, recipe_id, 118.0, 0.004, 47.0)
        print(sim.send(event, force_db_failure=True).text)
        return

    if fault == "RECIPE_MISMATCH":
        event = build_event("LOAD-01", "LOAD", lot_id, panel_id, recipe_id, 118.0, 0.004, 10.0)
        print("load", sim.send(event).text)
        event = build_event("CLEAN-01", "CLEAN", lot_id, panel_id, recipe_id, 118.0, 0.004, 18.0)
        print("clean", sim.send(event).text)
        base = sim.api_url.replace("/api/events", "")
        sim.client.post(
            f"{base}/api/commands",
            json={"command_type": "SELECT_RECIPE", "equipment_id": "PROC-01", "recipe_id": "RCP-OLED-B01"},
        )
        temp, pressure = sensors.reading(None)
        event = build_event("PROC-01", "EVAP", lot_id, panel_id, "RCP-OLED-B01", temp, pressure, 47.0)
        print(sim.send(event).text)
        return

    temp, pressure = sensors.reading(fault)
    event = build_event("PROC-01", "EVAP", lot_id, panel_id, recipe_id, temp, pressure, 47.0)
    print(sim.send(event).text)


def run_order(sim: EquipmentSimulator, api_url: str, work_order_id: Optional[str]) -> None:
    base = api_url.replace("/api/events", "")
    if not work_order_id:
        rows = sim.client.get(f"{base}/api/work-orders").json()
        if not rows:
            print("지시가 없다. Ops Console에서 먼저 투입한다.")
            return
        work_order_id = rows[0]["id"]
    orders = {row["id"]: row for row in sim.client.get(f"{base}/api/work-orders").json()}
    wo = orders.get(work_order_id)
    if wo is None:
        print(f"지시 없음: {work_order_id}")
        return
    lot_id = wo["lot_id"]
    recipe_id = wo["recipe_id"]
    sensors = SensorGenerator(recipe_id if recipe_id in RECIPES else "RCP-OLED-A01")
    print(json.dumps({"run_order": work_order_id, "lot": lot_id, "recipe": recipe_id}))
    for eq_id in ["LOAD-01", "CLEAN-01", "PROC-01", "PROC-02", "ENC-01", "PI-01", "LCD-01", "INSPECT-01"]:
        sim.client.post(f"{base}/api/commands", json={"command_type": "START", "equipment_id": eq_id})
    recipe_eq = ["CLEAN-01", "PROC-01", "PROC-02", "ENC-01"] if recipe_id.startswith("RCP-OLED") else ["PI-01", "LCD-01"]
    for eq_id in recipe_eq:
        sim.client.post(
            f"{base}/api/commands",
            json={"command_type": "SELECT_RECIPE", "equipment_id": eq_id, "recipe_id": recipe_id},
        )
    beats = Heartbeats(sim)
    beats.beat(force=True)
    for _ in range(80):
        beats.beat()
        info = sim.client.get(f"{base}/api/lots/{lot_id}/dispatch").json()
        if info.get("lot_status") == "HOLD":
            print("HOLD", info.get("lot_id"), "stop")
            return
        if info.get("done") or not info.get("next_step"):
            print("done", json.dumps(info))
            return
        step = info["next_step"]
        cycle = {"CLEAN": 18.0, "EVAP": 46.0, "ENCAP": 30.0, "PI": 22.0, "LCD_CELL": 40.0, "INSPECT": 12.0}.get(step)
        inspect = "PASS" if step == "INSPECT" else None
        temp, pressure = sensors.reading(None)
        event = build_event(
            info["next_equipment_id"],
            step,
            info["lot_id"],
            info["panel_id"],
            recipe_id,
            temp,
            pressure,
            cycle,
            inspect,
        )
        print(json.dumps({"send": info["next_equipment_id"], "step": step, "panel": info["panel_id"]}))
        res = sim.send(event)
        print(res.status_code, res.text)
        body = res.json()
        if not body.get("accepted"):
            return
        time.sleep(0.2)
    print("step limit")


def main() -> None:
    parser = argparse.ArgumentParser(description="DisplayFab Ops Lab equipment simulator")
    parser.add_argument("--api", default=API_URL)
    parser.add_argument(
        "--fault",
        choices=[
            "COMMUNICATION_LOSS",
            "TEMPERATURE_OUT_OF_RANGE",
            "PRESSURE_OUT_OF_RANGE",
            "RECIPE_MISMATCH",
            "INVALID_LOT",
            "INVALID_PANEL",
            "DUPLICATE_EVENT",
            "STALE_TIMESTAMP",
            "UNKNOWN_EQUIPMENT",
            "DB_WRITE_FAILURE",
            "PRODUCT_ROUTE",
            "SKIP_STEP",
            "HEARTBEAT",
        ],
    )
    parser.add_argument("--lot", default="LOT-20260918-001")
    parser.add_argument("--panel", default="PNL-00001")
    parser.add_argument("--recipe", default="RCP-OLED-A01")
    parser.add_argument("--loop", action="store_true", help="패널 001~005를 반복 투입")
    parser.add_argument("--run-order", nargs="?", const="", default=None, help="지시 ID. 생략하면 최신 지시")
    args = parser.parse_args()

    sim = EquipmentSimulator(args.api)
    try:
        if args.run_order is not None:
            run_order(sim, args.api, args.run_order or None)
            return
        host_prep(sim, args.api, args.recipe)
        if args.fault:
            run_fault(sim, args.fault, args.lot, args.panel, args.recipe)
            return
        if args.loop:
            for n in range(1, 6):
                run_normal(sim, args.lot, f"PNL-{n:05d}", args.recipe)
            return
        run_normal(sim, args.lot, args.panel, args.recipe)
    finally:
        sim.close()


if __name__ == "__main__":
    main()
