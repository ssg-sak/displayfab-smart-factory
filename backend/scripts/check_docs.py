"""문서에 적힌 링크와 파일 경로가 실제로 있는지 본다.

문서가 코드보다 늦게 썩는 걸 막는 최소 장치다.

  python scripts/check_docs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"\[[^\]]*\]\(([^)#]+)(?:#[^)]*)?\)")
SKIP_PREFIX = ("http://", "https://", "mailto:")


def main() -> int:
    broken: list[str] = []
    checked = 0
    for doc in sorted(ROOT.rglob("*.md")):
        if any(part in {"node_modules", ".git", "obj", "bin"} for part in doc.parts):
            continue
        for target in LINK.findall(doc.read_text(encoding="utf-8")):
            target = target.strip()
            if not target or target.startswith(SKIP_PREFIX):
                continue
            checked += 1
            if not (doc.parent / target).resolve().exists():
                broken.append(f"{doc.relative_to(ROOT)} → {target}")

    for line in broken:
        print("[깨짐]", line)
    print(f"링크 {checked}개 확인, 깨진 것 {len(broken)}개")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
