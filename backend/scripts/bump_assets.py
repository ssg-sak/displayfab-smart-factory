"""dashboard html의 ?v= 캐시 버전을 한 번에 올린다."""

import re
import sys
from pathlib import Path

version = sys.argv[1] if len(sys.argv) > 1 else "14"
root = Path(__file__).resolve().parents[2] / "dashboard"
for path in sorted(root.glob("*.html")):
    text = path.read_text(encoding="utf-8")
    bumped = re.sub(r"\?v=\d+", f"?v={version}", text)
    if bumped != text:
        path.write_text(bumped, encoding="utf-8")
        print("bumped", path.name)
