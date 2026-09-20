"""HTTP checks for a deployed image. --exercise resets the target demo DB."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--exercise", action="store_true", help="Erase demo data and run concurrent scenario/reset checks")
    parser.add_argument("--admin-env-file", type=Path)
    args = parser.parse_args()
    token = os.environ.get("DISPLAYFAB_ADMIN_TOKEN", "")
    if args.admin_env_file:
        for line in args.admin_env_file.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("DISPLAYFAB_ADMIN_TOKEN="):
                token = line.split("=", 1)[1].strip()
    if args.exercise and not token:
        parser.error("--exercise requires DISPLAYFAB_ADMIN_TOKEN or --admin-env-file")

    with httpx.Client(base_url=args.base, timeout=45) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        assert health.json()["db"] == "ok"
        for path in ("/", "/mes.html", "/lots.html", "/alarms.html", "/traceability.html", "/guide.html", "/app.js", "/styles.css", "/openapi.json"):
            response = client.get(path)
            response.raise_for_status()
            assert response.content, path
        equipment = client.get("/api/equipment")
        equipment.raise_for_status()
        assert len(equipment.json()) == 8
        print("PASS: health, 8 equipment, dashboard pages/assets, OpenAPI")

        if args.exercise:
            assert client.post("/api/lab/reset").status_code == 403
            assert client.post("/api/lab/reset", headers={"X-Admin-Token": "wrong"}).status_code == 403

            def reset():
                response = client.post("/api/lab/reset", headers={"X-Admin-Token": token})
                response.raise_for_status()
                assert response.json()["ok"] is True

            def scenario(name):
                response = client.post(f"/api/lab/scenarios/{name}/run")
                response.raise_for_status()
                assert response.json()["ok"] is True, response.json()

            # The old implementation can delete a WorkOrder while it is running.
            with ThreadPoolExecutor(max_workers=4) as pool:
                for _ in range(4):
                    futures = [
                        pool.submit(scenario, "demo_oled_pass"),
                        pool.submit(reset),
                        pool.submit(scenario, "demo_oled_fail"),
                        pool.submit(scenario, "demo_lcd_pass"),
                    ]
                    for future in futures:
                        future.result()
            reset()
            print("PASS: reset authentication and 4 rounds of concurrent reset/OLED/LCD requests")

        started = time.monotonic()
        response = client.get("/api/health")
        response.raise_for_status()
        print(json.dumps({"health": response.json(), "health_seconds": round(time.monotonic() - started, 3)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
