"""잠긴 디버그 스위치 - 켜지는 조건, 안 켜지는 조건, 꺼지는 조건."""

from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.debug_capture import MAX_REQUESTS, DebugCapture, DebugCaptureRule, build_debug_capture
from app.core.logging import JsonFormatter, RequestContextFilter
from app.db.base import Base
from app.models import AdminAuditLog, User

NOW = datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)


def settings(**overrides: Any) -> SimpleNamespace:
    base = dict(
        log_debug_bodies=True,
        log_debug_body_paths=("POST /api/trips/*",),
        log_debug_body_fields=("policyId", "memo", "password"),  # password 는 비밀 이름 - 무시된다
        log_debug_body_user="42",
        log_debug_body_until=(NOW + timedelta(hours=1)).isoformat(),
        log_debug_bodies_allow_protected=False,
        log_debug_operator_user_id="1",
        is_protected_env=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class AuditSpy:
    def __init__(self, *, fail_on: set[str] = frozenset()):
        self.calls: list[tuple[str, dict]] = []
        self.fail_on = fail_on

    def __call__(self, action: str, payload: dict) -> None:
        if action in self.fail_on:
            raise RuntimeError("audit down")
        self.calls.append((action, payload))


@pytest.fixture
def lines():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestContextFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    previous = root.level
    root.setLevel(logging.INFO)
    yield lambda: [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    root.removeHandler(handler)
    root.setLevel(previous)


def debug_lines(read) -> list[dict]:
    return [line for line in read() if line["kind"] == "debug"]


def build(audit: AuditSpy | None = None, *, now=lambda: NOW, **overrides) -> DebugCapture | None:
    return build_debug_capture(settings(**overrides), now=now, audit=audit or AuditSpy())


# --------------------------------------------------------------------------- 켜진 뒤
def test_captures_only_listed_non_secret_fields_for_matching_requests(lines):
    audit = AuditSpy()
    capture = build(audit)
    assert capture is not None and capture.active
    assert [action for action, _ in audit.calls] == ["log_debug_capture.start"]

    body = json.dumps({"policyId": 179, "memo": "hello", "password": "hunter2", "email": "x@example.com"}).encode()
    capture.observe(method="POST", path="/api/trips/17/policies", user_id=42, body=body)

    (line,) = debug_lines(lines)
    assert line["debug_body"] == {"policyId": 179, "memo": "hello"}
    dumped = json.dumps(line)
    assert "hunter2" not in dumped and "x@example.com" not in dumped


@pytest.mark.parametrize(
    "method, path, user_id",
    [
        ("PATCH", "/api/trips/17/policies", 42),  # 메서드 불일치
        ("POST", "/api/policies", 42),  # 경로 불일치
        ("POST", "/api/trips/17/policies", 7),  # 사용자 불일치
        ("POST", "/api/trips/17/policies", None),  # 익명
    ],
)
def test_non_matching_requests_are_not_captured(method, path, user_id, lines):
    capture = build()
    capture.observe(method=method, path=path, user_id=user_id, body=b'{"policyId": 1}')
    assert debug_lines(lines) == []


def test_auth_and_password_paths_are_excluded_even_if_the_rule_names_them(lines):
    capture = build(log_debug_body_paths=("POST /api/auth/*", "POST /api/me/password", "POST /api/trips/*"))
    for path in ("/api/auth/login", "/api/me/password", "/api/invites/abc"):
        capture.observe(method="POST", path=path, user_id=42, body=b'{"policyId": 1}')
    assert debug_lines(lines) == []


def test_place_paths_are_excluded_even_if_the_rule_names_them(lines):
    # 일정 장소 · 맞춰 보기 본문에는 카카오 장소값(이름 · 주소 · 좌표)이 온다 - 설정과 무관하게 남기지 않는다(카카오 운영정책)
    capture = build(log_debug_body_paths=("POST /api/places/*", "POST /api/trips/*", "PATCH /api/trips/*"))
    for method, path in (
        ("POST", "/api/places/match"),
        ("POST", "/api/trips/1/days/1/places"),
        ("POST", "/api/trips/1/days/1/places/batch"),
        ("PATCH", "/api/trips/1/places/2"),
    ):
        capture.observe(method=method, path=path, user_id=42, body=b'{"policyId": 1}')
    assert debug_lines(lines) == []
    capture.observe(method="POST", path="/api/trips/1/policies", user_id=42, body=b'{"policyId": 1}')
    assert len(debug_lines(lines)) == 1   # 장소가 아닌 일정 경로는 그대로 잡는다


def test_incomplete_or_non_object_bodies_are_skipped(lines):
    capture = build()
    capture.observe(method="POST", path="/api/trips/1/policies", user_id=42, body=None)
    capture.observe(method="POST", path="/api/trips/1/policies", user_id=42, body=b"[1,2]")
    capture.observe(method="POST", path="/api/trips/1/policies", user_id=42, body=b"{bad")
    assert debug_lines(lines) == []
    capture.observe(method="POST", path="/api/trips/1/policies", user_id=42, body=b"x" * 20_000)
    assert debug_lines(lines)[-1]["debug_body"] == "too_large"


# --------------------------------------------------------------------------- 꺼지는 조건
def test_expiry_is_checked_on_receive_and_again_right_before_emit(lines):
    clock = {"now": NOW}
    audit = AuditSpy()
    capture = build(audit, now=lambda: clock["now"])

    clock["now"] = NOW + timedelta(hours=2)  # 수신 시점에 이미 만료
    capture.observe(method="POST", path="/api/trips/1/policies", user_id=42, body=b'{"policyId": 1}')
    assert not capture.active and capture.stop_reason == "expired"
    assert debug_lines(lines) == []
    assert audit.calls[-1][0] == "log_debug_capture.stop" and audit.calls[-1][1]["reason"] == "expired"

    # 수신 시점엔 유효했지만 출력 직전에 만료된 경우 - 시계가 검사 사이에 넘어간다
    ticks = iter([NOW, NOW + timedelta(hours=5)])
    capture2 = build(now=lambda: next(ticks, NOW + timedelta(hours=5)))
    capture2.observe(method="POST", path="/api/trips/1/policies", user_id=42, body=b'{"policyId": 1}')
    assert not capture2.active and capture2.stop_reason == "expired"
    assert debug_lines(lines) == []


def test_request_limit_stops_capture_with_an_audit_entry(lines):
    audit = AuditSpy()
    capture = build(audit)
    for _ in range(MAX_REQUESTS):
        capture.observe(method="POST", path="/api/trips/1/policies", user_id=42, body=b'{"policyId": 1}')
    assert not capture.active and capture.stop_reason == "limit"
    assert len(debug_lines(lines)) == MAX_REQUESTS
    assert audit.calls[-1][1]["captured"] == MAX_REQUESTS


def test_audit_failure_at_start_keeps_capture_off():
    assert build(AuditSpy(fail_on={"log_debug_capture.start"})) is None


def test_audit_failure_at_stop_still_leaves_capture_off():
    capture = build(AuditSpy(fail_on={"log_debug_capture.stop"}))
    capture.stop("manual")
    assert not capture.active


# --------------------------------------------------------------------------- 안 켜지는 조건
@pytest.mark.parametrize(
    "overrides",
    [
        {"log_debug_body_paths": ()},
        {"log_debug_body_paths": ("/api/trips/*",)},  # 메서드 없음
        {"log_debug_body_fields": ("password", "token")},  # 비밀 이름만
        {"log_debug_body_until": ""},
        {"log_debug_body_until": (NOW + timedelta(hours=1)).replace(tzinfo=None).isoformat()},  # 시간대 없음
        {"log_debug_body_until": (NOW + timedelta(hours=5)).isoformat()},  # 4시간 초과
        {"log_debug_body_until": (NOW - timedelta(minutes=1)).isoformat()},  # 이미 지남
        {"log_debug_operator_user_id": ""},
        {"log_debug_operator_user_id": "abc"},
        {"is_protected_env": True, "log_debug_bodies_allow_protected": False},
        {"is_protected_env": True, "log_debug_bodies_allow_protected": True, "log_debug_body_user": ""},  # 보호 환경은 사용자 필수
    ],
)
def test_missing_or_invalid_settings_keep_capture_off(overrides, caplog):
    with caplog.at_level(logging.WARNING):
        assert build(**overrides) is None
    assert any("Debug capture stays OFF" in record.getMessage() for record in caplog.records)


def test_switch_off_means_none_without_warning(caplog):
    with caplog.at_level(logging.WARNING):
        assert build(log_debug_bodies=False) is None
    assert not caplog.records


def test_protected_env_with_user_and_flag_turns_on():
    capture = build(is_protected_env=True, log_debug_bodies_allow_protected=True, log_debug_body_user="42")
    assert capture is not None and capture.active


# --------------------------------------------------------------------------- 운영자 검증 + 실제 감사 로그 (sqlite)
@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _user(user_id: int, role: str) -> User:
    return User(id=user_id, email=f"u{user_id}@example.com", nickname=f"u{user_id}", role=role, onboarding_completed=True,
                created_at=datetime(2026, 9, 22), updated_at=datetime(2026, 9, 22))


def test_operator_must_be_an_existing_admin(session_factory, caplog):
    with session_factory() as db:
        db.add_all([_user(1, "admin"), _user(2, "user")])
        db.commit()
    with caplog.at_level(logging.WARNING):
        assert build_debug_capture(settings(log_debug_operator_user_id="2"), now=lambda: NOW, session_factory=session_factory) is None
        assert build_debug_capture(settings(log_debug_operator_user_id="9"), now=lambda: NOW, session_factory=session_factory) is None
    assert sum("existing admin" in record.getMessage() for record in caplog.records) == 2

    capture = build_debug_capture(settings(log_debug_operator_user_id="1"), now=lambda: NOW, session_factory=session_factory)
    assert capture is not None and capture.active
    capture.stop("manual")
    with session_factory() as db:
        rows = db.query(AdminAuditLog).order_by(AdminAuditLog.id).all()
    assert [row.action for row in rows] == ["log_debug_capture.start", "log_debug_capture.stop"]
    assert all(row.admin_user_id == 1 and row.target_type == "log_debug_capture" for row in rows)
    assert rows[1].after_json["reason"] == "manual"


def test_without_a_database_the_capture_stays_off(caplog):
    with caplog.at_level(logging.WARNING):
        assert build_debug_capture(settings(), now=lambda: NOW, session_factory=None) is None
    assert any("database is required" in record.getMessage() for record in caplog.records)


def test_rule_describe_has_no_field_values():
    rule = DebugCaptureRule(matchers=(("POST", "/x"),), fields=frozenset({"a"}), user_id=1, until=NOW, operator_user_id=1)
    assert rule.describe() == {"paths": ["POST /x"], "fields": ["a"], "userId": 1, "until": NOW.isoformat()}
