"""잠긴 디버그 스위치 - 재현할 때만, 지정한 경로·사용자·필드의 요청 본문 값을 stdout 에 남긴다.

계획 Task 7: docs/superpowers/plans/2026-09-22-caddy-service-status-log.md

설정이 전부 있어야 켜진다. 하나라도 빠지면 경고 한 줄 남기고 꺼진 채 기동한다 - 잘못 켜져서 도는 일이 없게.
- 보호 환경(staging·prod)에서는 대상 사용자와 ALLOW_PROTECTED 가 필수다.
- 만료는 시간대가 있어야 하고 최대 4시간. 요청 수신 시점과 출력 시점 둘 다 재확인한다.
- 인증·비밀번호·토큰·초대 경로는 설정과 무관하게 제외. 비밀 이름 필드는 FIELDS 에 적어도 안 찍힌다.
- 응답 본문은 구조적으로 못 본다(observe 는 요청 본문 복사본만 받는다).
- 시작·종료를 admin_audit_logs 에 남긴다. 감사 기록이 실패하면 캡처는 켜지지 않는다 / 즉시 꺼진다.
- 출력은 같은 stdout(kind=debug). 같은 회전·같은 보존이다. 별도 보존은 로그 드라이버 쪽에서 따로 구성한다.
"""

from __future__ import annotations

import fnmatch
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.request_context import is_secret_field

logger = logging.getLogger(__name__)
debug_logger = logging.getLogger("debug_capture")

MAX_ACTIVE = timedelta(hours=4)
MAX_REQUESTS = 200
MAX_BODY_BYTES = 16 * 1024
ALWAYS_EXCLUDED_PREFIXES = ("/api/auth/", "/api/invites")
# place: 일정 장소 · 통합 검색 · 맞춰 보기 본문에는 카카오 장소값(이름 · 주소 · 좌표)이 온다 - 설정과 무관하게 남기지 않는다(카카오 운영정책)
ALWAYS_EXCLUDED_MARKERS = ("password", "token", "invite", "reset", "place")
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

AuditWriter = Callable[[str, dict[str, Any]], None]  # (action, payload). 실패하면 예외를 던진다.
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class DebugCaptureRule:
    matchers: tuple[tuple[str, str], ...]  # (METHOD, 경로 glob)
    fields: frozenset[str]
    user_id: int | None
    until: datetime  # aware
    operator_user_id: int

    def describe(self) -> dict[str, Any]:
        return {
            "paths": [f"{method} {pattern}" for method, pattern in self.matchers],
            "fields": sorted(self.fields),
            "userId": self.user_id,
            "until": self.until.isoformat(),
        }


class DebugCapture:
    def __init__(self, rule: DebugCaptureRule, *, audit: AuditWriter, now: Clock) -> None:
        self.rule = rule
        self._audit = audit
        self._now = now
        self.count = 0
        self.active = False
        self.stop_reason: str | None = None

    def start(self) -> bool:
        try:
            self._audit("log_debug_capture.start", self.rule.describe())
        except Exception:
            logger.exception("Debug capture stays OFF: audit log could not be written")
            return False
        self.active = True
        logger.warning("Debug capture ON until %s: %s", self.rule.until.isoformat(), self.rule.describe())
        return True

    def stop(self, reason: str) -> None:
        if not self.active:
            return
        self.active = False
        self.stop_reason = reason
        logger.warning("Debug capture OFF (%s) after %d captured requests", reason, self.count)
        try:
            self._audit("log_debug_capture.stop", {**self.rule.describe(), "reason": reason, "captured": self.count})
        except Exception:
            logger.exception("Debug capture stop audit could not be written")

    def _expired(self) -> bool:
        return self._now() >= self.rule.until

    def matches(self, method: str, path: str, user_id: int | None) -> bool:
        lowered = path.lower()
        if lowered.startswith(ALWAYS_EXCLUDED_PREFIXES) or any(marker in lowered for marker in ALWAYS_EXCLUDED_MARKERS):
            return False
        if self.rule.user_id is not None and user_id != self.rule.user_id:
            return False
        return any(method == rule_method and fnmatch.fnmatchcase(path, pattern) for rule_method, pattern in self.rule.matchers)

    def observe(self, *, method: str, path: str, user_id: int | None, body: bytes | None) -> None:
        """미들웨어가 요청이 끝날 때 부른다. body 는 완전히 수신한 복사본이거나 None."""
        if not self.active:
            return
        if self._expired():
            self.stop("expired")
            return
        if not self.matches(method, path, user_id) or body is None:
            return
        if len(body) > MAX_BODY_BYTES:
            selected: Any = "too_large"
        else:
            try:
                parsed = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                return
            if not isinstance(parsed, dict):
                return
            selected = {key: value for key, value in parsed.items() if key in self.rule.fields and not is_secret_field(key)}
        if self._expired():  # 출력 직전 재확인
            self.stop("expired")
            return
        debug_logger.info(
            "captured request body",
            extra={"kind": "debug", "log_fields": {"method": method, "path": path, "debug_body": selected}},
        )
        self.count += 1
        if self.count >= MAX_REQUESTS:
            self.stop("limit")


def _parse_matchers(values: tuple[str, ...], problems: list[str]) -> tuple[tuple[str, str], ...]:
    matchers = []
    for raw in values:
        parts = raw.split(None, 1)
        if len(parts) != 2 or parts[0].upper() not in HTTP_METHODS or not parts[1].startswith("/"):
            problems.append(f"LOG_DEBUG_BODY_PATHS entry must look like 'POST /api/trips/*': {raw!r}")
            continue
        matchers.append((parts[0].upper(), parts[1]))
    if not matchers:
        problems.append("LOG_DEBUG_BODY_PATHS is required")
    return tuple(matchers)


def _parse_until(value: str, now: datetime, problems: list[str]) -> datetime | None:
    if not value:
        problems.append("LOG_DEBUG_BODY_UNTIL is required")
        return None
    try:
        until = datetime.fromisoformat(value)
    except ValueError:
        problems.append("LOG_DEBUG_BODY_UNTIL must be ISO 8601")
        return None
    if until.tzinfo is None:
        problems.append("LOG_DEBUG_BODY_UNTIL must include a timezone offset")
        return None
    if until <= now:
        problems.append("LOG_DEBUG_BODY_UNTIL is already past")
    elif until - now > MAX_ACTIVE:
        problems.append(f"LOG_DEBUG_BODY_UNTIL may be at most {MAX_ACTIVE} from now")
    return until


def _parse_int(value: str, name: str, problems: list[str], *, required: bool) -> int | None:
    if not value:
        if required:
            problems.append(f"{name} is required")
        return None
    try:
        return int(value)
    except ValueError:
        problems.append(f"{name} must be an integer")
        return None


def _db_audit(session_factory: Callable[[], Any], operator_user_id: int) -> AuditWriter:
    from app.repositories import admin as admin_repository

    def write(action: str, payload: dict[str, Any]) -> None:
        db = session_factory()
        try:
            admin_repository.add_audit_log(
                db,
                admin_user_id=operator_user_id,
                action=action,
                target_type="log_debug_capture",
                target_id=payload.get("until", ""),
                summary=f"{action} {', '.join(payload.get('paths', []))}",
                before_json=None,
                after_json=payload,
            )
            db.commit()
        finally:
            db.close()

    return write


def _operator_is_admin(session_factory: Callable[[], Any], operator_user_id: int) -> bool:
    from app.models import User

    db = session_factory()
    try:
        user = db.get(User, operator_user_id)
        return user is not None and getattr(user, "role", "user") == "admin"
    finally:
        db.close()


def build_debug_capture(
    settings: Any,
    *,
    now: Clock = lambda: datetime.now(timezone.utc),
    session_factory: Callable[[], Any] | None = None,
    audit: AuditWriter | None = None,
) -> DebugCapture | None:
    """설정을 검증해 캡처를 만든다. 조건이 하나라도 빠지면 None - 꺼진 채 기동."""
    if not getattr(settings, "log_debug_bodies", False):
        return None

    problems: list[str] = []
    current = now()
    matchers = _parse_matchers(tuple(settings.log_debug_body_paths), problems)
    fields = frozenset(name for name in settings.log_debug_body_fields if not is_secret_field(name))
    if not fields:
        problems.append("LOG_DEBUG_BODY_FIELDS is required (secret-looking names are ignored)")
    protected = bool(getattr(settings, "is_protected_env", False))
    user_id = _parse_int(settings.log_debug_body_user, "LOG_DEBUG_BODY_USER", problems, required=protected)
    until = _parse_until(settings.log_debug_body_until, current, problems)
    if protected and not settings.log_debug_bodies_allow_protected:
        problems.append("LOG_DEBUG_BODIES_ALLOW_PROTECTED=1 is required in a protected environment")
    operator_id = _parse_int(settings.log_debug_operator_user_id, "LOG_DEBUG_OPERATOR_USER_ID", problems, required=True)

    if operator_id is not None and audit is None:
        if session_factory is None:
            problems.append("a database is required to verify the operator and write audit logs")
        elif not _operator_is_admin(session_factory, operator_id):
            problems.append("LOG_DEBUG_OPERATOR_USER_ID must be an existing admin user")

    if problems or until is None or operator_id is None:
        logger.warning("Debug capture stays OFF: %s", "; ".join(problems) or "invalid configuration")
        return None

    rule = DebugCaptureRule(matchers=matchers, fields=fields, user_id=user_id, until=until, operator_user_id=operator_id)
    writer = audit if audit is not None else _db_audit(session_factory, operator_id)  # type: ignore[arg-type]
    capture = DebugCapture(rule, audit=writer, now=now)
    return capture if capture.start() else None
