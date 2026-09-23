"""요청마다 request_id 를 만들고 모든 로그 줄에 붙이는 ASGI 미들웨어.

계획: docs/superpowers/plans/2026-09-22-caddy-service-status-log.md

- contextvar 에는 값이 아니라 RequestLogContext **객체**를 넣는다. 인증 의존성(get_current_user)은 동기 함수라
  스레드풀에서 도는데, 스레드 안의 ContextVar.set 은 요청 태스크로 돌아오지 않지만 같은 객체의 속성 변경은 보인다.
- 본문은 선취하지 않는다. 하위 앱이 receive 를 부를 때 그대로 넘기고 관측용 복사본만 64KB 까지 든다.
- 응답이 시작된 뒤의 예외에는 두 번째 응답을 보내지 않는다.
- 쿼리는 화이트리스트 이름만 남긴다. 새 파라미터는 기본 제외다.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import secrets
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)
access_logger = logging.getLogger("access")

QUERY_ALLOWLIST = frozenset({"limit", "offset", "region", "style", "status", "sourceCategory", "source_type", "target_type"})
QUERY_VALUE_MAX = 64
NO_QUERY_PREFIXES = ("/api/auth/",)
SECRET_FIELD_MARKERS = ("password", "token", "secret", "authorization", "refresh")
BODY_COPY_MAX = 64 * 1024
BODY_SHAPE_MAX_KEYS = 40
BODY_SHAPE_KEY_MAX = 64
REQUEST_ID_HEADER = "x-request-id"
_UPSTREAM_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_TRACE_ROOT_PATTERN = re.compile(r"(?:^|;)Root=([A-Za-z0-9-]{1,64})(?:;|$)")


@dataclass
class RequestLogContext:
    request_id: str
    trace_id: str | None = None
    user_id: int | None = None


_current: ContextVar[RequestLogContext | None] = ContextVar("request_log_context", default=None)


def current_context() -> RequestLogContext | None:
    return _current.get()


def new_request_id() -> str:
    return secrets.token_hex(8)


def note_current_user(request: Any, user: Any) -> None:
    """인증 의존성이 부른다. 객체 속성만 바꾸므로 스레드풀에서 실행돼도 요청 태스크에 보인다."""
    context = getattr(getattr(request, "state", None), "log_context", None)
    user_id = getattr(user, "id", None)
    if isinstance(context, RequestLogContext) and user_id is not None:
        context.user_id = int(user_id)


def is_secret_field(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in SECRET_FIELD_MARKERS)


def filtered_query(path: str, raw_query: bytes) -> dict[str, str] | None:
    """화이트리스트 이름만. /api/auth/* 는 통째로 None (OAuth code·state 가 여기 있다)."""
    if path.startswith(NO_QUERY_PREFIXES):
        return None
    if not raw_query:
        return {}
    kept: dict[str, str] = {}
    for key, value in parse_qsl(raw_query.decode("latin-1"), keep_blank_values=True):
        if key in QUERY_ALLOWLIST:
            kept[key] = value[:QUERY_VALUE_MAX]
    return kept


def mask_network(value: str) -> str | None:
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    prefix = 24 if address.version == 4 else 48
    return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))


def _headers(scope: Scope) -> dict[str, str]:
    return {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}


def _shape_value(name: str, value: Any) -> str:
    if is_secret_field(name):
        return "str(*)" if isinstance(value, str) else "*"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return f"str({len(value)})"
    if isinstance(value, list):
        return f"list({len(value)})"
    if isinstance(value, dict):
        return f"object({len(value)})"
    return type(value).__name__


def _known_body_fields(scope: Scope) -> set[str]:
    """라우트가 선언한 Pydantic 본문 모델의 필드명. 그 밖의 키는 이름을 남기지 않는다(임의 키가 개인정보일 수 있다)."""
    route = scope.get("route")
    dependant = getattr(route, "dependant", None)
    names: set[str] = set()
    for param in getattr(dependant, "body_params", None) or []:
        model = getattr(param, "type_", None) or getattr(getattr(param, "field_info", None), "annotation", None)
        fields = getattr(model, "model_fields", None)
        if isinstance(fields, dict):
            names.update(fields.keys())
            for info in fields.values():
                alias = getattr(info, "alias", None)
                if alias:
                    names.add(alias)
    return names


def body_shape(scope: Scope, copy: bytes, *, overflow: bool, read: bool, complete: bool) -> Any:
    if not read:
        return "unread"
    if overflow:
        return "too_large"
    if not complete:
        return "incomplete"
    if not copy:
        return None
    try:
        parsed = json.loads(copy)
    except (ValueError, UnicodeDecodeError):
        return "invalid_json" if _looks_like_json(scope) else "non_json"
    if not isinstance(parsed, dict):
        return "non_object"
    known = _known_body_fields(scope)
    shape: dict[str, Any] = {}
    unknown = 0
    for index, (key, value) in enumerate(parsed.items()):
        if index >= BODY_SHAPE_MAX_KEYS:
            shape["truncated_keys"] = len(parsed) - BODY_SHAPE_MAX_KEYS
            break
        if not isinstance(key, str) or len(key) > BODY_SHAPE_KEY_MAX or key not in known:
            unknown += 1
            continue
        shape[key] = _shape_value(key, value)
    if unknown:
        shape["unknown_keys"] = unknown
    return shape


def _looks_like_json(scope: Scope) -> bool:
    return "json" in _headers(scope).get("content-type", "")


class RequestContextMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        trusted_proxy_cidrs: tuple[str, ...] = (),
        exclude_paths: tuple[str, ...] = ("/api/health", "/health"),
        admin_domain: str = "",
        debug_capture: Any = None,  # app.core.debug_capture.DebugCapture | None - 잠긴 디버그 스위치
    ) -> None:
        self.app = app
        self.trusted_networks = tuple(ipaddress.ip_network(cidr, strict=False) for cidr in trusted_proxy_cidrs if cidr)
        self.exclude_paths = frozenset(exclude_paths)
        self.admin_domain = admin_domain.strip().lower()
        self.debug_capture = debug_capture

    def _from_trusted_proxy(self, scope: Scope) -> bool:
        client = scope.get("client")
        if not client or not self.trusted_networks:
            return False
        try:
            address = ipaddress.ip_address(client[0])
        except ValueError:
            return False
        return any(address in network for network in self.trusted_networks)

    def _client_net(self, headers: dict[str, str], trusted: bool) -> str | None:
        if not trusted:
            return None
        forwarded = headers.get("cf-connecting-ip") or headers.get("x-forwarded-for", "").split(",")[0]
        return mask_network(forwarded) if forwarded else None

    def _site(self, headers: dict[str, str]) -> str:
        host = headers.get("host", "").split(":")[0].lower()
        return "admin" if self.admin_domain and host == self.admin_domain else "app"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        trusted = self._from_trusted_proxy(scope)
        # 엣지(Caddy)가 만든 ID 를 그대로 쓴다 - 하나의 ID 로 엣지·백엔드 로그가 같이 검색된다.
        # Caddy 는 클라이언트가 보낸 X-Request-Id 를 덮어쓰므로 위조 값이 여기까지 오지 못한다.
        # 신뢰 프록시가 아니거나 형식이 틀리면 자체 생성한다(직접 접근·AWS ALB 경로).
        incoming = headers.get(REQUEST_ID_HEADER, "")
        adopted = incoming if trusted and _UPSTREAM_ID_PATTERN.match(incoming) else None
        context = RequestLogContext(request_id=adopted or new_request_id())
        trace_match = _TRACE_ROOT_PATTERN.search(headers.get("x-amzn-trace-id", ""))
        if trace_match:
            context.trace_id = trace_match.group(1)

        state = scope.setdefault("state", {})
        state["log_context"] = context
        token = _current.set(context)

        path = scope.get("path", "")
        method = scope.get("method", "")
        started = time.perf_counter()
        response: dict[str, Any] = {"started": False, "status": None}
        body: dict[str, Any] = {"copy": bytearray(), "overflow": False, "read": False, "complete": False}
        outcome = "ok"

        async def wrapped_receive() -> Message:
            message = await receive()
            if message["type"] == "http.request":
                body["read"] = True
                chunk = message.get("body", b"")
                if not body["overflow"]:
                    if len(body["copy"]) + len(chunk) <= BODY_COPY_MAX:
                        body["copy"].extend(chunk)
                    else:
                        body["overflow"] = True
                        body["copy"].clear()
                if not message.get("more_body", False):
                    body["complete"] = True
            return message

        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                response["started"] = True
                response["status"] = message.get("status")
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", context.request_id.encode("ascii")))
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            outcome = "error"
            logger.exception("Unhandled error while handling %s %s", method, path)
            if response["started"]:
                raise  # 이미 응답이 나갔다. 두 번째 응답은 없다.
            response["status"] = 500
            payload = json.dumps({"detail": "Internal Server Error", "requestId": context.request_id}).encode("utf-8")
            await wrapped_send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode("ascii"))],
                }
            )
            await wrapped_send({"type": "http.response.body", "body": payload})
        finally:
            _current.reset(token)
            if path not in self.exclude_paths:
                status = response["status"]
                fields: dict[str, Any] = {
                    "method": method,
                    "path": path,
                    "query": filtered_query(path, scope.get("query_string", b"")),
                    "status": status,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "client_net": self._client_net(headers, trusted),
                    "site": self._site(headers),
                    "outcome": outcome,
                }
                if status is not None and status >= 400 and method in {"POST", "PUT", "PATCH", "DELETE"}:
                    fields["body_shape"] = body_shape(
                        scope, bytes(body["copy"]), overflow=body["overflow"], read=body["read"], complete=body["complete"]
                    )
                access_logger.info(
                    "%s %s %s",
                    method,
                    path,
                    status if status is not None else outcome,
                    extra={"kind": "access", "log_fields": fields, "log_context": context},
                )
            if self.debug_capture is not None:
                # 완전히 수신한 복사본만 넘긴다. 미수신·초과·불완전은 None - 값을 찍을 근거가 없다.
                complete_copy = bytes(body["copy"]) if body["complete"] and not body["overflow"] else None
                _current_token = _current.set(context)  # debug 줄에도 request_id 가 붙게
                try:
                    self.debug_capture.observe(method=method, path=path, user_id=context.user_id, body=complete_copy)
                finally:
                    _current.reset(_current_token)
