"""README에 넣을 화면을 실제 서버에서 찍는다.

화면을 고친 뒤 다시 찍으면 문서 이미지가 같이 갱신된다.
서버를 돌리는 데는 필요 없는 도구라서 requirements.txt에 넣지 않았다.

  python -m pip install -r requirements-dev.txt
  python -m playwright install chromium
  python scripts/shoot_screens.py --base http://127.0.0.1:8000

찍기 직전에 설비 생존신호를 한 번 보낸다. 안 보내면 10초 규칙에 걸려
모든 설비가 "줄 끊김"인 화면이 찍힌다.
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

LINE_EQUIPMENT = [
    "LOAD-01",
    "CLEAN-01",
    "PROC-01",
    "PROC-02",
    "ENC-01",
    "PI-01",
    "LCD-01",
    "INSPECT-01",
]

SHOTS = [
    # 운전 화면은 한 화면에 다 보이게 만든 관제 화면이다. full_page로 찍으면 레이아웃이 늘어난다.
    ("/", "ops-console.png", "운전 화면", False),
    ("/mes.html", "production-oee.png", "생산 화면 + OEE", True),
    ("/alarms.html", "alarms-anomaly.png", "알람 + 이상 점수", True),
    ("/traceability.html", "traceability.png", "유리 한 장의 지나온 길", True),
]


def wake_line(client: httpx.Client) -> None:
    """생존신호를 한 바퀴 보낸다. 측정값은 실제 설비처럼 조금씩 흔들리게 둔다."""
    now = datetime.now(timezone.utc).isoformat()
    for equipment_id in LINE_EQUIPMENT:
        client.post(
            "/api/events",
            json={
                "equipment_id": equipment_id,
                "event_type": "HEARTBEAT",
                "equipment_status": "RUN",
                "chamber_temperature": round(random.gauss(118.4, 0.45), 2),
                "vacuum_pressure": round(random.gauss(0.0041, 0.00009), 5),
                "timestamp": now,
            },
            headers={"X-Request-Id": str(uuid.uuid4())},
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--warmup",
        type=int,
        default=14,
        help="찍기 전에 보낼 생존신호 바퀴 수. 이상 점수는 표본 10개부터 판단한다",
    )
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else Path(__file__).resolve().parents[2] / "docs" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    client = httpx.Client(base_url=args.base, timeout=20.0)
    if client.get("/api/health").json().get("db") != "ok":
        print("호스트가 준비되지 않았다. docker compose up -d 후 서버를 켠다.")
        return 1

    for _ in range(max(args.warmup, 0)):
        wake_line(client)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
        for path, filename, label, full_page in SHOTS:
            wake_line(client)
            page.goto(args.base + path, wait_until="networkidle")
            page.wait_for_timeout(3000)
            target = out_dir / filename
            page.screenshot(path=str(target), full_page=full_page)
            print(f"{label:24} {target}")
        browser.close()

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
