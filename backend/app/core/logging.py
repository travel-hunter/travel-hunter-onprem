"""stdout JSON 로깅. 한 줄 = 한 레코드. request_id·user_id 는 필터가 붙인다.

- 예외는 타입·메시지(앞 500자, 마스킹)·app/ 아래 프레임 위치만. 지역 변수·소스 줄은 남기지 않는다.
- uvicorn.access 는 끈다 - 쿼리스트링을 그대로 찍어 토큰이 샌다. 접근 줄은 request_context 가 만든다.
- sqlalchemy.engine·httpx 는 WARNING - 파라미터·URL 을 INFO 로 흘리지 않게.
"""

from __future__ import annotations

import json
import logging
import logging.config
import re
import traceback
from datetime import datetime, timedelta, timezone
from types import TracebackType
from typing import Any

from app.core import request_context

KST = timezone(timedelta(hours=9))
MESSAGE_MAX = 2000
EXC_MESSAGE_MAX = 500
FRAMES_MAX = 20
CAUSE_CHAIN_MAX = 3
_SECRET_PAIR = re.compile(r"(?i)\b(token|key|password|passwd|secret|code|state|authorization)=[^&\s'\"]+")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def mask_text(value: str, limit: int) -> str:
    masked = _SECRET_PAIR.sub(lambda m: f"{m.group(1)}=***", value)
    masked = _EMAIL.sub("***@***", masked)
    return masked if len(masked) <= limit else masked[:limit] + "…"


def _frames(tb: TracebackType | None) -> list[str]:
    frames = []
    for frame in traceback.extract_tb(tb):
        filename = frame.filename.replace("\\", "/")
        if "/app/" not in filename and not filename.startswith("app/"):
            continue
        short = filename[filename.rfind("/app/") + 1 :] if "/app/" in filename else filename
        frames.append(f"{short}:{frame.lineno}:{frame.name}")
    return frames[-FRAMES_MAX:]


def serialize_exception(exc_info: tuple[type[BaseException], BaseException, TracebackType | None] | Any) -> dict[str, Any]:
    exc_type, exc, tb = exc_info
    payload: dict[str, Any] = {
        "exc_type": exc_type.__name__ if exc_type else None,
        "exc_message": mask_text(str(exc), EXC_MESSAGE_MAX),
        "frames": _frames(tb),
    }
    causes = []
    current = exc.__cause__ or exc.__context__ if exc else None
    while current is not None and len(causes) < CAUSE_CHAIN_MAX:
        causes.append({"exc_type": type(current).__name__, "exc_message": mask_text(str(current), EXC_MESSAGE_MAX)})
        current = current.__cause__ or current.__context__
    if causes:
        payload["causes"] = causes
    return payload


class RequestContextFilter(logging.Filter):
    """레코드에 request_id·trace_id·user_id 를 붙인다. 접근 줄은 contextvar 가 이미 reset 된 뒤 나오므로 extra 를 우선 본다."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = getattr(record, "log_context", None) or request_context.current_context()
        record.request_id = getattr(context, "request_id", None)
        record.trace_id = getattr(context, "trace_id", None)
        record.user_id = getattr(context, "user_id", None)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).astimezone(KST).isoformat(timespec="milliseconds"),
            "kind": getattr(record, "kind", "app"),
            "level": record.levelname,
            "logger": record.name,
            "msg": mask_text(record.getMessage(), MESSAGE_MAX),
            "request_id": getattr(record, "request_id", None),
            "trace_id": getattr(record, "trace_id", None),
            "user_id": getattr(record, "user_id", None),
        }
        fields = getattr(record, "log_fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info and record.exc_info[0] is not None:
            payload.update(serialize_exception(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def logging_config(level: str = "INFO") -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"request_context": {"()": "app.core.logging.RequestContextFilter"}},
        "formatters": {"json": {"()": "app.core.logging.JsonFormatter"}},
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "json",
                "filters": ["request_context"],
            }
        },
        "root": {"level": level.upper(), "handlers": ["stdout"]},
        "loggers": {
            "uvicorn": {"level": "INFO", "handlers": ["stdout"], "propagate": False},
            "uvicorn.error": {"level": "INFO", "handlers": ["stdout"], "propagate": False},
            # 끈다 - 요청 줄(쿼리 포함)을 그대로 찍는다. 접근 줄은 request_context 가 담당한다.
            "uvicorn.access": {"level": "CRITICAL", "handlers": [], "propagate": False},
            "sqlalchemy.engine": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
        },
    }


def configure_logging(level: str = "INFO") -> None:
    logging.config.dictConfig(logging_config(level))
