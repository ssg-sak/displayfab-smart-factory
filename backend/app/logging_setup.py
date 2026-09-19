"""request_id / event_id를 로그에 붙여 한 이벤트의 경로를 추적한다."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Optional

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
event_id_var: ContextVar[str] = ContextVar("event_id", default="-")


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.event_id = event_id_var.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s request_id=%(request_id)s event_id=%(event_id)s %(message)s"
        )
    )
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def bind_request_id(value: str) -> None:
    request_id_var.set(value)


def bind_event_id(value: Optional[str]) -> None:
    event_id_var.set(value or "-")
