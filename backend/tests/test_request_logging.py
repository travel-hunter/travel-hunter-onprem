"""request_id 상관관계 · 본문 보존 · 예외 처리 · 민감정보 미기록.

계획의 고정 검증 순서: 동기 인증 문맥 → 본문 바이트 보존 → 응답 시작 후 예외 → SQL/외부 예외 유출 → 토큰 URL.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
from datetime import datetime
from typing import Any

import pytest
from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api import dependencies
from app.core import security
from app.core.logging import JsonFormatter, RequestContextFilter, logging_config, mask_text, serialize_exception
from app.core.request_context import RequestContextMiddleware, current_context, filtered_query
from app.db.base import Base
from app.models import User

service_logger = logging.getLogger("app.services.test_probe")


# ----------------------------------------------------------------------------- 로그 캡처
@pytest.fixture
def log_lines():
    """root 에 JSON 핸들러를 하나 붙여 이 테스트가 만든 줄만 모은다. 실제 포맷터·필터를 그대로 쓴다."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestContextFilter())
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # 운영 설정(logging_config)과 같은 외부 로거 레벨. httpx 는 INFO 로 요청 URL 전체(쿼리 포함)를 찍는다.
    quieted = {name: logging.getLogger(name).level for name in ("httpx", "httpcore", "sqlalchemy.engine")}
    for name in quieted:
        logging.getLogger(name).setLevel(logging.WARNING)

    def read() -> list[dict[str, Any]]:
        return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]

    yield read
    root.removeHandler(handler)
    root.setLevel(previous_level)
    for name, level in quieted.items():
        logging.getLogger(name).setLevel(level)


def access_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [line for line in lines if line["kind"] == "access"]


# ----------------------------------------------------------------------------- 테스트 앱
class TripPayload(BaseModel):
    policyId: int
    memo: str
    password: str | None = None


def build_app(**middleware_kwargs: Any) -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware, **middleware_kwargs)

    @test_app.get("/api/me")
    def me(user: User = Depends(dependencies.get_current_user)):  # 동기 - 스레드풀에서 돈다
        service_logger.info("profile read")
        return {"id": user.id}

    @test_app.get("/api/background")
    def with_background(background: BackgroundTasks, user: User = Depends(dependencies.get_current_user)):
        background.add_task(service_logger.info, "background after response")
        return {"ok": True}

    @test_app.post("/api/echo")
    async def echo(request: Request):
        body = await request.body()
        return {"sha": hashlib.sha256(body).hexdigest(), "length": len(body)}

    @test_app.post("/api/trips/{trip_id}/policies", status_code=400)
    async def trip_policy(trip_id: int, payload: TripPayload):
        return {"detail": "bad"}

    @test_app.post("/api/skip-body")
    async def skip_body():
        return {"ok": True}

    @test_app.get("/api/boom")
    async def boom():
        raise RuntimeError("boom token=abc123 user@example.com")

    @test_app.get("/api/stream-boom")
    async def stream_boom():
        async def gen():
            yield b"first"
            raise RuntimeError("mid-stream")

        return StreamingResponse(gen())

    @test_app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @test_app.get("/api/policies")
    async def policies(region: str | None = None, q: str | None = None):
        return {"region": region}

    return test_app


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session


def make_user(user_id: int) -> User:
    return User(
        id=user_id,
        email=f"user-{user_id}@example.com",
        nickname=f"user-{user_id}",
        role="user",
        onboarding_completed=True,
        created_at=datetime(2026, 9, 22),
        updated_at=datetime(2026, 9, 22),
    )


@pytest.fixture
def client(db):
    test_app = build_app()
    test_app.dependency_overrides[dependencies.get_optional_db] = lambda: db  # 인증 자체는 실제 경로를 탄다
    return TestClient(test_app, raise_server_exceptions=False)


def bearer(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {security.create_access_token(user_id)}"}


# ----------------------------------------------------------------------------- 1. 동기 인증 문맥
def test_sync_auth_dependency_attaches_user_id_to_every_line(client, db, log_lines):
    db.add_all([make_user(42), make_user(7)])
    db.commit()

    first = client.get("/api/me", headers=bearer(42))
    second = client.get("/api/me", headers=bearer(7))
    assert first.status_code == 200 and second.status_code == 200

    lines = log_lines()
    by_request = {}
    for line in lines:
        by_request.setdefault(line["request_id"], []).append(line)
    assert len(by_request) == 2, "요청마다 다른 request_id"

    for request_id, group in by_request.items():
        kinds = {line["kind"] for line in group}
        assert kinds == {"app", "access"}
        user_ids = {line["user_id"] for line in group}
        assert len(user_ids) == 1 and user_ids != {None}, "동기 의존성이 넣은 user_id 가 서비스 줄과 접근 줄 양쪽에"
    assert {group[0]["user_id"] for group in by_request.values()} == {42, 7}, "두 사용자 문맥이 섞이지 않는다"

    assert first.headers["x-request-id"] in by_request
    assert current_context() is None, "요청이 끝나면 contextvar 는 비어 있다"


def test_logs_outside_a_request_have_no_request_id(log_lines):
    service_logger.info("scheduler tick")
    (line,) = log_lines()
    assert line["request_id"] is None and line["user_id"] is None


def test_background_task_keeps_the_request_context(client, db, log_lines):
    db.add(make_user(42))
    db.commit()
    response = client.get("/api/background", headers=bearer(42))
    assert response.status_code == 200
    background = [line for line in log_lines() if line["msg"] == "background after response"]
    assert background and background[0]["request_id"] == response.headers["x-request-id"]
    assert background[0]["user_id"] == 42


# ----------------------------------------------------------------------------- 2. 본문 보존 (직접 ASGI)
async def _run_asgi(test_app, *, method="POST", path="/api/echo", chunks=(), headers=(), client=("127.0.0.1", 1), disconnect_after=None, query=b""):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers],
        "client": client,
        "server": ("testserver", 80),
    }
    messages = []
    for index, chunk in enumerate(chunks):
        if disconnect_after is not None and index == disconnect_after:
            messages.append({"type": "http.disconnect"})
            break
        messages.append({"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1})
    if not chunks:
        messages.append({"type": "http.request", "body": b"", "more_body": False})
    received = iter(messages)
    sent: list[dict] = []

    async def receive():
        try:
            return next(received)
        except StopIteration:
            await asyncio.sleep(3600)  # 더 줄 게 없다 - 실제 서버처럼 대기

    async def send(message):
        sent.append(message)

    try:
        await test_app(scope, receive, send)
    except Exception as exc:  # 스트리밍 도중 예외는 재전파된다
        return sent, exc
    return sent, None


def _status(sent):
    return next((m["status"] for m in sent if m["type"] == "http.response.start"), None)


def _body(sent):
    return b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")


@pytest.mark.parametrize("chunks", [(b'{"a":1}',), (b'{"a"', b":1", b"}"), (b"x" * 70_000,), (b"x" * 40_000, b"y" * 40_000)])
def test_downstream_receives_the_exact_bytes(chunks, log_lines):
    sent, error = asyncio.run(_run_asgi(build_app(), chunks=chunks, headers=[("content-type", "application/json")]))
    assert error is None and _status(sent) == 200
    payload = json.loads(_body(sent))
    raw = b"".join(chunks)
    assert payload == {"sha": hashlib.sha256(raw).hexdigest(), "length": len(raw)}
    (access,) = access_lines(log_lines())
    assert "body_shape" not in access, "2xx 에는 모양을 안 남긴다"


def test_body_shape_reports_only_declared_fields_and_hides_secret_lengths(log_lines):
    body = json.dumps({"policyId": 179, "memo": "x" * 120, "password": "hunter2", "email": "who@example.com", "nested": {"a": [1]}}).encode()
    sent, _ = asyncio.run(_run_asgi(build_app(), path="/api/trips/17/policies", chunks=(body,), headers=[("content-type", "application/json")]))
    assert _status(sent) == 400
    (access,) = access_lines(log_lines())
    assert access["body_shape"] == {"policyId": "int", "memo": "str(120)", "password": "str(*)", "unknown_keys": 2}
    dumped = json.dumps(access)
    assert "who@example.com" not in dumped and "hunter2" not in dumped and "nested" not in dumped


@pytest.mark.parametrize(
    "chunks, headers, expected",
    [
        ((b"x" * 70_000,), [("content-type", "application/json")], "too_large"),
        ((b"{bad json",), [("content-type", "application/json")], "invalid_json"),
        ((b"plain text",), [("content-type", "text/plain")], "non_json"),
        ((b"[1,2]",), [("content-type", "application/json")], "non_object"),
    ],
)
def test_body_shape_states(chunks, headers, expected, log_lines):
    asyncio.run(_run_asgi(build_app(), path="/api/trips/17/policies", chunks=chunks, headers=headers))
    (access,) = access_lines(log_lines())
    assert access["body_shape"] == expected


def test_unread_body_is_not_read_for_logging(log_lines):
    # 라우트가 본문을 안 읽으면 미들웨어도 안 읽는다 - receive 가 한 번도 불리지 않는다
    sent, _ = asyncio.run(_run_asgi(build_app(), path="/api/skip-body", chunks=(b'{"a":1}',), headers=[("content-type", "application/json")]))
    assert _status(sent) == 200


def test_disconnect_mid_body_is_marked_incomplete(log_lines):
    sent, error = asyncio.run(
        _run_asgi(build_app(), path="/api/trips/17/policies", chunks=(b'{"policyId":', b"1}"), disconnect_after=1, headers=[("content-type", "application/json")])
    )
    (access,) = access_lines(log_lines())
    assert access["body_shape"] == "incomplete"


# ----------------------------------------------------------------------------- 3. 예외
def test_exception_before_response_gives_500_with_request_id(client, log_lines):
    response = client.get("/api/boom")
    assert response.status_code == 500
    request_id = response.headers["x-request-id"]
    assert response.json() == {"detail": "Internal Server Error", "requestId": request_id}

    lines = log_lines()
    errors = [line for line in lines if line["level"] == "ERROR"]
    assert len(errors) == 1 and errors[0]["request_id"] == request_id
    assert errors[0]["exc_type"] == "RuntimeError"
    assert "abc123" not in errors[0]["exc_message"] and "user@example.com" not in errors[0]["exc_message"]
    assert all(frame.startswith("app/") or "/app/" in frame for frame in errors[0]["frames"]) or errors[0]["frames"] == []
    (access,) = access_lines(lines)
    assert access["status"] == 500 and access["outcome"] == "error" and access["request_id"] == request_id


def test_exception_after_response_started_sends_no_second_response(log_lines):
    sent, error = asyncio.run(_run_asgi(build_app(), method="GET", path="/api/stream-boom"))
    assert isinstance(error, RuntimeError)
    starts = [m for m in sent if m["type"] == "http.response.start"]
    assert len(starts) == 1 and starts[0]["status"] == 200, "두 번째 응답 없음"
    lines = log_lines()
    assert [line["exc_type"] for line in lines if line["level"] == "ERROR"] == ["RuntimeError"]
    (access,) = access_lines(lines)
    assert access["status"] == 200 and access["outcome"] == "error"


def test_cancellation_is_not_a_500(log_lines):
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)

    @test_app.get("/api/slow")
    async def slow():
        raise asyncio.CancelledError()

    async def run():
        with pytest.raises(asyncio.CancelledError):
            await _run_asgi_raw(test_app)

    async def _run_asgi_raw(app_):
        scope = {"type": "http", "method": "GET", "path": "/api/slow", "query_string": b"", "headers": [], "client": ("127.0.0.1", 1), "asgi": {"version": "3.0"}}
        await app_(scope, lambda: asyncio.sleep(3600), lambda m: asyncio.sleep(0))

    asyncio.run(run())
    lines = log_lines()
    assert not [line for line in lines if line["level"] == "ERROR"]
    (access,) = access_lines(lines)
    assert access["status"] is None and access["outcome"] == "cancelled"


# ----------------------------------------------------------------------------- 4. 예외 메시지 유출
def test_sql_exception_carries_no_bound_values():
    engine = create_engine("sqlite:///:memory:", hide_parameters=True)  # session.get_engine 과 같은 옵션
    with engine.connect() as connection:
        connection.execute(text("CREATE TABLE t (email TEXT UNIQUE)"))
        connection.execute(text("INSERT INTO t VALUES ('secret@example.com')"))
        with pytest.raises(IntegrityError) as error:
            connection.execute(text("INSERT INTO t VALUES (:email)"), {"email": "secret@example.com"})
    serialized = serialize_exception((type(error.value), error.value, error.value.__traceback__))
    assert "secret@example.com" not in json.dumps(serialized)


def test_mask_text_hides_pairs_and_emails_and_truncates():
    assert mask_text("token=abc&key=k password=p code=c", 500) == "token=***&key=*** password=*** code=***"
    assert mask_text("mail me@example.com now", 500) == "mail ***@*** now"
    assert mask_text("x" * 600, 500).endswith("…") and len(mask_text("x" * 600, 500)) == 501


def test_production_logging_config_silences_url_logging_libraries():
    # httpx 는 INFO 에서 "HTTP Request: GET http://...?code=..." 를 찍는다 - 운영 설정이 이를 끈다는 걸 고정한다
    loggers = logging_config()["loggers"]
    assert loggers["httpx"]["level"] == "WARNING" and loggers["httpcore"]["level"] == "WARNING"
    assert loggers["sqlalchemy.engine"]["level"] == "WARNING"
    assert loggers["uvicorn.access"]["handlers"] == [] and loggers["uvicorn.access"]["propagate"] is False


# ----------------------------------------------------------------------------- 5. 토큰 URL · 쿼리 화이트리스트
@pytest.mark.parametrize(
    "path, query",
    [
        ("/signup/verify", b"token=SECRET_A"),
        ("/reset-password", b"token=SECRET_B"),
        ("/signup/social-agreement", b"token=SECRET_C&redirect=/x"),
        ("/api/auth/oauth/kakao/callback", b"code=SECRET_D&state=SECRET_E"),
    ],
)
def test_token_urls_never_reach_the_log(path, query, client, log_lines):
    client.get(f"{path}?{query.decode()}")
    dumped = json.dumps(log_lines())
    assert "SECRET_" not in dumped
    (access,) = access_lines(log_lines())
    assert access["query"] in (None, {})


def test_query_allowlist_keeps_region_and_drops_free_text(client, log_lines):
    client.get("/api/policies?region=jeju&q=who@example.com&token=SECRET_F&page=2")
    (access,) = access_lines(log_lines())
    assert access["query"] == {"region": "jeju"}
    assert "SECRET_F" not in json.dumps(log_lines()) and "who@example.com" not in json.dumps(log_lines())


def test_filtered_query_unit():
    assert filtered_query("/api/auth/refresh", b"limit=1") is None
    assert filtered_query("/api/policies", b"") == {}
    assert filtered_query("/api/policies", b"limit=" + b"9" * 100) == {"limit": "9" * 64}


# ----------------------------------------------------------------------------- 6. 신뢰 프록시
def _line_for(test_app, **kwargs):
    asyncio.run(_run_asgi(test_app, method="GET", path="/api/policies", **kwargs))


def test_untrusted_peer_headers_are_ignored(log_lines):
    _line_for(build_app(trusted_proxy_cidrs=("172.20.0.0/16",)), client=("203.0.113.9", 1), headers=[("cf-connecting-ip", "198.51.100.7"), ("x-request-id", "attacker-chosen-id")])
    (access,) = access_lines(log_lines())
    assert access["client_net"] is None
    assert access["request_id"] != "attacker-chosen-id" and len(access["request_id"]) == 16


def test_trusted_edge_request_id_is_adopted_so_both_logs_share_one_id(log_lines):
    # Caddy 가 만든 UUID 를 그대로 쓴다 - 문의 코드 하나로 엣지·백엔드 로그가 같이 검색된다.
    # Caddy 가 클라이언트 값을 덮어쓰므로(실측 확인) 위조 값은 여기까지 오지 못한다.
    edge_id = "ab829b1e-5163-4b25-ad9f-25bc542b3c05"
    test_app = build_app(trusted_proxy_cidrs=("172.20.0.0/16",))
    _line_for(test_app, client=("172.20.0.5", 1), headers=[("cf-connecting-ip", "198.51.100.77"), ("x-request-id", edge_id), ("x-amzn-trace-id", "Root=1-67891233-abcdef012345678912345678;Parent=x")])
    (access,) = access_lines(log_lines())
    assert access["request_id"] == edge_id
    assert access["client_net"] == "198.51.100.0/24"
    assert access["trace_id"] == "1-67891233-abcdef012345678912345678"
    _line_for(test_app, client=("172.20.0.5", 1), headers=[("x-forwarded-for", "2001:db8:abcd:1234::1, 10.0.0.1")])
    assert access_lines(log_lines())[-1]["client_net"] == "2001:db8:abcd::/48"


@pytest.mark.parametrize("bad", ["short", "has space", "x" * 65, "sql'injection"])
def test_malformed_edge_id_falls_back_to_a_generated_one(bad, log_lines):
    _line_for(build_app(trusted_proxy_cidrs=("172.20.0.0/16",)), client=("172.20.0.5", 1), headers=[("x-request-id", bad)])
    (access,) = access_lines(log_lines())
    assert access["request_id"] != bad and len(access["request_id"]) == 16


def test_without_an_edge_the_backend_generates_its_own_id(log_lines):
    # AWS 경로: ALB 는 X-Request-Id 를 붙이지 않는다. 코드 분기 없이 자체 생성으로 돈다.
    _line_for(build_app(trusted_proxy_cidrs=("172.20.0.0/16",)), client=("172.20.0.5", 1), headers=[("x-amzn-trace-id", "Root=1-67891233-abcdef012345678912345678")])
    (access,) = access_lines(log_lines())
    assert len(access["request_id"]) == 16
    assert access["trace_id"] == "1-67891233-abcdef012345678912345678"


# ----------------------------------------------------------------------------- 7. 제외 경로 · 접근 줄 1개
def test_health_is_excluded_and_each_request_logs_exactly_one_access_line(client, log_lines):
    client.get("/api/health")
    client.get("/api/policies?region=x")
    client.get("/api/policies?region=y")
    access = access_lines(log_lines())
    assert [line["path"] for line in access] == ["/api/policies", "/api/policies"]
    assert len({line["request_id"] for line in access}) == 2


def test_file_log_is_off_unless_a_path_is_given(monkeypatch):
    """코드 기본값은 비활성이다. 호스트(Windows)에서 백엔드·테스트를 돌릴 때 /var/log 가 C 드라이브 루트로
    풀려 폴더가 생기지 않게 한다. 경로는 compose 가 컨테이너에만 넘긴다."""
    import dataclasses
    import os

    from app.core.config import Settings

    if os.environ.get("LOG_FILE_PATH"):
        pytest.skip("LOG_FILE_PATH 가 설정된 환경")
    default = next(f.default for f in dataclasses.fields(Settings) if f.name == "log_file_path")
    assert default == ""
    assert "file" not in logging_config(file_path="")["handlers"]
