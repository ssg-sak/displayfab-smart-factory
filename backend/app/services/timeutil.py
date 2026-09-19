from datetime import datetime, timezone


def utcnow() -> datetime:
    """저장/비교는 naive UTC로 통일한다. aware/naive 혼선이 STALE 오판의 원인이다."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
