"""공개 주소에서 쓰기 요청이 쏟아지는 걸 막는다.

한 프로세스 안의 메모리 계수기다. 서버가 여러 대로 늘어나면 각자 센다.
시연 한 대를 지키는 용도라서 그 정도로 충분하다. 0이면 제한 없음이고
로컬과 테스트는 항상 0이다.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

WINDOW_SEC = 60.0


class WriteRateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and now - hits[0] > WINDOW_SEC:
            hits.popleft()
        if len(hits) >= self.per_minute:
            return False
        hits.append(now)
        return True

    def retry_after(self, key: str, now: float | None = None) -> int:
        hits = self._hits.get(key)
        if not hits:
            return 1
        now = time.monotonic() if now is None else now
        return max(1, int(WINDOW_SEC - (now - hits[0])) + 1)


def client_key(headers, client_host: str | None) -> str:
    """프록시(Render) 뒤에서는 원래 주소가 헤더 첫 칸에 온다."""

    forwarded = headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return client_host or "unknown"
