# 역추적용 구조화 로그 계획 — request_id 상관관계

상태: 계획 rev5 (코덱스 2차 리뷰 반영). 코드 없음. 승인 뒤 구현.
브랜치: `feature/service-access-log` (origin/develop `e148b7c` 기준, 새 워크트리)

목적은 **역추적** — 사용자가 문제를 겪었을 때 그 요청에 무슨 일이 있었는지 로그로 되짚어 해결하는 것.
사용자 결정(2026-09-22): 조회는 **터미널**, 내부 `user_id` **기록**, 보관은 **용량 회전 200MB/서비스**(30일은 목표, 보장 아님), 민감정보는 **단계 원칙**, Task 6 **최소 범위 포함**.

## 왜 — 지금은 역추적이 불가능하고, 이미 새고 있다

| 필요 | 현재 (실측) |
|---|---|
| 요청 ID | 없음 |
| 구조화 앱 로그 | **logging 설정 없음.** `logger.exception`은 최후 핸들러로 형식 없이 stderr |
| 실제 경로·사용자 | uvicorn access 줄만 |
| 보존 | `json-file` 회전 없음 → 무한 증가 |
| **토큰 미유출** | uvicorn access 줄이 쿼리스트링을 그대로 찍는다. `?token=LEAKTEST123` → `docker logs`에 그대로. OAuth `?code=&state=`가 dev·prod에 남는 중 |
| SQL 파라미터 | `create_engine(..., pool_pre_ping=True)` — `hide_parameters` 없음. 예외 메시지에 바인딩 값이 실린다 |

dev-server 8시간 실측: 1,733줄 중 1,589줄이 `/api/health`. 실제 요청 ~450줄/일.

## AWS 목표 구조와의 관계

백엔드가 stdout에 JSON 한 줄씩 → on-prem `json-file`, AWS `awslogs` → CloudWatch. 파일·DB·화면 없음. 이전 때 버릴 코드 없음.
ALB의 `X-Amzn-Trace-Id`는 `Root=1-...;` 형식의 복합 헤더라 **별도 필드 `trace_id`로 파싱**해 둔다(request_id로 쓰지 않는다).

## 역추적 흐름

```
scripts/trace-request.sh user:42 --since 48h
  → 15:02:11  POST /api/trips/17/policies  500  312ms  request_id=a1b2c3d4e5f6a7b8
scripts/trace-request.sh a1b2c3d4e5f6a7b8
  → 15:02:11.101  INFO   app.api.routes.trips   link policy 179 to trip 17
  → 15:02:11.410  ERROR  app.services.trips     IntegrityError (스택 프레임)
  → 15:02:11.412  ACCESS POST /api/trips/17/policies 500
```

## 로그 줄

```json
{"ts":"2026-09-22T15:02:11.412+09:00","kind":"access","request_id":"a1b2c3d4e5f6a7b8","trace_id":null,"user_id":42,
 "method":"POST","path":"/api/trips/17/policies","query":{"limit":"20"},"status":500,"duration_ms":312,
 "client_net":"203.0.113.0/24","site":"app","body_shape":{"policyId":"int","memo":"str(120)"}}
{"ts":"...","kind":"app","request_id":"a1b2c3d4e5f6a7b8","user_id":42,"level":"ERROR","logger":"app.services.trips",
 "msg":"...","exc_type":"IntegrityError","exc_message":"(앞 500자, 마스킹 후)","frames":["app/services/trips.py:210:link_policy", "..."]}
```

## 민감정보 — 단계 원칙 (확정)

**기본은 열쇠만, 오류엔 모양, 꼭 필요하면 좁은 범위·짧은 시간·감사 기록 남기고 값. 그보다 먼저 로컬 재현.**

| 단계 | 무엇 |
|---|---|
| 1 | 로그의 `user_id`·`request_id`·시각·경로로 **DB에서 찾는다**. 개인정보를 두 곳에 두지 않는다 |
| 2 | 4xx·5xx일 때 본문의 **알려진 필드명·타입·길이만** (`body_shape`). 값 없음 |
| 3 | **잠긴 디버그 스위치**(Task 7). 재현할 때만 |
| 4 | `request_id`로 알아낸 조건으로 **로컬 재현** (3보다 먼저) |

### 무엇을 남기고 무엇을 안 남기나

| 남긴다 | 절대 안 남긴다 |
|---|---|
| 경로 전체 | **응답 본문**(모든 단계) · 요청 본문 값(기본; Task 7만 예외) |
| 쿼리 — **화이트리스트 이름만** | 이메일·닉네임·자유 텍스트(`q`·`query`·`redirect`·`preferredRegions`) |
| 내부 정수 `user_id` | 요청·응답 헤더 전부 |
| `/24`·`/48` 마스킹 IP (신뢰 프록시 경유 시만) | 원본 IP |

**쿼리 화이트리스트**(실측한 19개 파라미터 중): `limit` `offset` `region` `style` `status` `sourceCategory` `source_type` `target_type`.
값은 64자로 자른다. 이 밖의 이름은 **기록하지 않는다**(블랙리스트 아님 — 새 파라미터는 기본 제외). `/api/auth/*`는 `query: null`.

**예외 메시지 정책** (쿼리·본문 필터를 우회하는 경로):
- 엔진 `hide_parameters=True` — SQL 예외에 바인딩 값이 안 실린다.
- `exc_message`는 앞 500자 + 마스킹 패턴(`(token|key|password|secret|code)=[^&\s]+`, 이메일 형태) 적용. 원인 체인(`__cause__`)도 같은 규칙으로 최대 3단.
- 스택은 **프레임 위치만**(`파일:줄:함수`, `app/` 아래만 최대 20개). 지역 변수·소스 줄은 안 남긴다.
- 외부 라이브러리 로거: `sqlalchemy.engine`·`httpx`·`httpcore` → `WARNING`. `uvicorn.access` 비활성.
- 이건 방어층이지 보장이 아니다. "외부 API 호출 시 URL에 키를 넣지 않는다"를 코드 규칙으로 적고, `httpx` 호출부를 구현 중 한 번 훑는다.

## 구조

```
요청 → Caddy ──(stdout, 필드 화이트리스트, 모든 요청)──▶ json-file 20m×10
        │
        └─▶ backend  [ServerError] → [CORS] → [RequestContext] → [ExceptionMiddleware] → 라우트
                                          │
                                          ├─ 요청마다 RequestLogContext 객체 생성 → contextvar + request.state, finally reset
                                          ├─ 인증 의존성이 그 객체의 user_id 를 갱신 (동기 스레드에서도 객체 참조라 보인다)
                                          ├─ receive 래핑: 통과시키며 ≤64KB 복사만
                                          ├─ send 래핑: response_started 추적
                                          └─ finally 에 접근 줄 1개
```

## 작업

### Task 1 — 로깅 기반 `app/core/logging.py`
- `dictConfig`: root → stdout, JSON 포맷터, `INFO`. `RequestContextFilter`가 contextvar의 컨텍스트 객체에서 `request_id`·`trace_id`·`user_id`를 읽어 부착.
- 예외 직렬화: 위 "예외 메시지 정책" 그대로.
- 외부 로거 레벨 조정. `uvicorn.error` 유지, **`uvicorn.access` 끔**(`--no-access-log`).
- `app/db/session.py`: `create_engine(..., hide_parameters=True)`.

### Task 2 — 요청 컨텍스트 미들웨어 `app/core/request_context.py`

**컨텍스트 객체.** `@dataclass class RequestLogContext: request_id, trace_id, user_id=None, ...` — 요청마다 새로 만든다. contextvar에는 이 **객체**를 넣는다.
`get_current_user`(`dependencies.py:14`)는 동기 함수라 스레드풀에서 돈다 — 스레드 안의 `ContextVar.set`은 요청 태스크로 돌아오지 않지만 **같은 객체의 속성 변경은 보인다.**
인증 의존성은 `request.state.log_context.user_id = user.id` 한 줄. 전역 공유 객체·가변 기본값 금지. 미들웨어 `finally`에서 `reset(token)`.

**request_id.** 항상 서버가 생성(`secrets.token_hex(8)`, 16자). 들어온 `X-Request-Id`는 `^[A-Za-z0-9._-]{8,64}$`이고 **신뢰 프록시에서 온 연결일 때만** `upstream_id`로 별도 보관. `X-Amzn-Trace-Id`는 `Root=` 값만 `trace_id`로. 형식이 틀리면 버린다.

**IP.** `scope["client"]`가 `TRUSTED_PROXY_CIDRS`(설정; on-prem은 compose 네트워크 대역, AWS는 ALB 서브넷) 안일 때만 `Cf-Connecting-Ip` → `X-Forwarded-For` 첫 값을 읽어 `/24`·`/48`. 아니면 `client_net: null`. Caddy의 `trusted_proxies`와 별개로 백엔드가 자체 판단한다.

**receive 래핑.** 하위 앱이 `receive`를 부를 때만 원 메시지를 읽어 **그대로 전달**(`body`·`more_body`·`http.disconnect` 불변). 관측 복사본만 누적 64KB까지; 초과 시 복사본 폐기 후 `body_shape: "too_large"`. 앱이 안 읽은 본문은 로그 때문에 읽지 않는다(`"unread"`). `more_body` 끝을 못 본 채 응답이 끝나면 `"incomplete"`. JSON 파싱 실패 `"invalid_json"`, 비JSON `"non_json"`.

**body_shape.** 4xx·5xx이고 완전 수신한 JSON 객체일 때만. **라우트의 Pydantic 본문 모델 필드명**(`route.dependant.body_params`)에 있는 키만 `이름: 타입(길이)`로, 모델 밖 키는 `unknown_keys: N`. 최상위만, 최대 40키, 키 64자. 비밀 이름(`password`·`token`·`secret`·`authorization`·`refresh`) 필드는 길이도 `*`.

**send 래핑 + 예외.** `http.response.start` 전송 여부를 추적.
- 응답 시작 **전** 예외: ERROR 줄(`request_id` 포함) → 500 JSON `{"detail":"Internal Server Error","requestId":...}`.
- 응답 시작 **후** 예외(스트리밍·BackgroundTask): ERROR 줄만, 두 번째 응답 안 보냄, 재전파.
- `asyncio.CancelledError`·클라이언트 단절: 500 아님. 접근 줄 `status: null, outcome: "disconnected"`, 재전파.
- 접근 줄은 `finally`에서 **정확히 1개**. 예외 로그 책임은 이 미들웨어. `HTTPException`은 `ExceptionMiddleware`가 처리하므로 여기 안 온다.
- **등록 순서**: `add_middleware`는 마지막 등록이 바깥이다. `RequestContext`를 **먼저** 등록하고 CORS를 나중에 등록해 CORS가 바깥 → 500에도 CORS 헤더가 붙는다. `expose_headers=["X-Request-Id"]`.
- `/api/health` 제외(`ACCESS_LOG_EXCLUDE_PATHS`). `site`: Host가 `ADMIN_DOMAIN`이면 `admin`.

### Task 3 — compose 회전 + Caddy stdout
- `compose.yaml` backend·caddy·frontend: `logging: {driver: json-file, options: {max-size: "20m", max-file: "10"}}`.
  **용량 회전이다.** 200MB 상한 안에서 트래픽에 따라 며칠~수개월 남는다. "30일"은 목표이지 보장이 아니고, 디버그 줄도 같은 조건이다. 보장은 AWS 로그 그룹 보존에서.
- Caddy snippet(두 파일): `log { output stdout  format filter { wrap json  fields { request>uri regexp \?.*$ ""  request>headers delete  resp_headers delete  request>remote_ip delete  request>remote_port delete  request>client_ip ip_mask { ipv4 24  ipv6 48 } } } }` + 전역 `servers { trusted_proxies static <cloudflared 대역>  client_ip_headers Cf-Connecting-Ip }`.
  **모든 요청을 기록한다**(필드는 화이트리스트). 목적은 백엔드가 죽었을 때의 502가 어딘가엔 남게 하는 것.

### Task 4 — 조회 스크립트
- `scripts/trace-request.sh <request_id | user:<id>> [--since 48h] [--sensitive]` — 시간순, 프레임 펼침. `--sensitive` 없으면 `kind=debug` 줄 숨김 — **출력 편의일 뿐 접근 통제가 아니다.** `docker logs`로는 그대로 보인다.
- `scripts/access-log-summary.sh [--since 24h]` — 시간대×상태군 count/avg/max, 5xx 상위 경로, 최근 5xx 20줄.

### Task 5 — 테스트 `tests/test_request_logging.py`
고정 순서(코덱스 권고): **동기 인증 문맥 → 본문 바이트 보존 → 응답 시작 후 예외 → SQL/외부 예외 유출 → 디버그 만료·감사 실패**.
1. 동기 `get_current_user` 경로로 인증한 요청의 접근 줄과 서비스 `logger.*` 줄에 `user_id` 있음. 동시 두 사용자 요청의 문맥 분리. 스케줄러 로그에 `request_id` 없음. 요청 중 만든 백그라운드 태스크는 문맥을 **복사**해 가진다(요청 종료 후 reset에 영향받지 않음).
2. 본문: 여러 청크 · 64KB 초과 · 중도 단절 · 미소비 · 잘못된 JSON · 깊은 중첩 · 비JSON — 하위 앱이 받는 바이트가 원본과 동일하고 `body_shape` 상태값이 맞다. 모델 밖 키는 이름이 안 나온다.
3. 라우트 예외(응답 전) → ERROR + 500 + `requestId` + CORS 헤더. 스트리밍 도중 예외 → 두 번째 응답 없음. `CancelledError` → 500 아님.
4. `hide_parameters`로 SQL 예외에 값 없음. `exc_message`에 `token=`·이메일이 마스킹. 프레임에 소스 줄 없음.
5. 토큰 URL 4종 → `token`·`code`·`state` 값 없음. `?region=x&q=이메일@x` → `region`만.
6. 비신뢰 피어의 `X-Request-Id`·`Cf-Connecting-Ip` 무시. 신뢰 피어 → `upstream_id`·`client_net`. `X-Amzn-Trace-Id` → `trace_id`만.
7. `/api/health` 제외. 접근 줄 정확히 1개.
8. **실제 uvicorn 기동** 후 stdout을 파싱 — caplog가 아니라 프로세스 출력. uvicorn access 줄 없음.
9. Caddy 블록 컨테이너 실측.

### Task 6 — 프런트 문의 코드 (최소 범위, 확정)
- `client.ts:54` `ApiError`에 `requestId: string | null` 추가 — throw 지점(`client.ts:123`)에서 `response.headers.get("X-Request-Id")`(교차 출처라 `expose_headers` 필요).
- 최종 실패 응답의 ID만 **기존 오류 UI**에 "문의 코드: …"로. 토스트 재설계 없음. 네트워크 단절(응답 없음)은 코드 없음.
- 콘솔에 응답 본문·헤더를 덤프하지 않는다.

### Task 7 — 잠긴 디버그 스위치 `app/core/debug_capture.py`
설정 전부 있어야 켜진다. 하나라도 빠지면 **꺼진 채 기동 + 경고 한 줄.**

| 설정 | 규칙 |
|---|---|
| `LOG_DEBUG_BODIES=1` | 스위치 |
| `LOG_DEBUG_BODY_PATHS` | 경로 glob **+ 메서드**(`POST /api/trips/*`). 필수 |
| `LOG_DEBUG_BODY_FIELDS` | 기록할 필드명 명시. 필수. 없는 필드는 안 찍힌다 |
| `LOG_DEBUG_BODY_USER` | 대상 user_id. **보호 환경에서는 필수**, 로컬은 선택 |
| `LOG_DEBUG_BODY_UNTIL` | 시간대 포함 ISO(`2026-09-23T18:00+09:00`). 필수. 기동 시각 + **최대 4시간** 초과면 거부 |
| `LOG_DEBUG_BODIES_ALLOW_PROTECTED=1` | `settings.is_protected_env`(property)면 필수 |
| `LOG_DEBUG_OPERATOR_USER_ID` | 감사 로그 주체. 필수. 기동 시 DB에서 **존재하고 admin인지 검증**, 아니면 꺼짐 |

- `/api/auth/*`·비밀번호·토큰·초대 경로는 설정과 무관하게 제외. 비밀 이름 필드는 `FIELDS`에 적어도 안 찍힌다.
- 요청당 16KB, **전체 200건** 도달 시 자동 종료. 만료는 요청 수신 시점과 **로그 출력 시점 둘 다** 재확인.
- 응답 본문은 어떤 설정에서도 안 찍는다.
- 시작·종료(만료·상한·기동 실패) 시 `admin_audit_logs`(`admin_user_id`는 NOT NULL → 위 운영자 id). **감사 기록 실패 → 캡처 즉시 비활성.**
- 출력은 같은 stdout `kind=debug`. **같은 회전·같은 보존이다.** AWS에서 별도 그룹·짧은 보존을 원하면 로그 드라이버/에이전트에서 `kind`로 라우팅을 **따로 구성해야** 한다 — 자동이 아니다.

테스트 `tests/test_debug_capture.py`: 조건 충족 시 지정 필드만 · 경로/메서드/사용자 불일치 · 만료(수신 시·출력 시) · 4시간 초과 거부 · 보호 환경 플래그 없음 · 운영자 id 검증 실패 · 200건 상한 · 감사 실패 시 비활성 · 응답 본문 부재.

## 검증
1. `pytest backend/tests` 전체, 프런트 typecheck·build·vitest.
2. 로컬 스택 재생성 → **실제 uvicorn stdout**이 전부 JSON, access 줄 없음, `?token=` 후 grep 0.
3. 일부러 500 → `trace-request.sh`로 프레임까지. 스트리밍 응답 중 예외 재현.
4. dev-server 재생성 후 2·3 반복. prod는 별도 승인.

## AWS 이전 시 (범위 밖)
- 미들웨어·로깅 그대로. Caddy 블록 삭제. `awslogs`, 로그 그룹 보존 30일(여기서 보장). `TRUSTED_PROXY_CIDRS`를 ALB 서브넷으로.
- `kind=debug` 별도 그룹은 에이전트 라우팅으로 따로 구성.
- ALB·CloudFront 접근 로그는 쿼리를 못 거른다 → 토큰을 쿼리에서 빼는 별도 계획.

## 하지 않는 것
- 파일 로그·DB 표·관리자 화면·Loki·Grafana·알림.
- 본문 상시 로깅. 응답 본문 로깅(모든 단계).
- 토큰 쿼리 제거(별도). prod 적용(별도 승인).

## rev4.1 → rev5 (코덱스 2차)
| 지적 | 반영 |
|---|---|
| 동기 인증에서 contextvar.set 역전파 안 됨 | 요청별 **컨텍스트 객체**, 의존성은 속성 갱신, finally reset, 분리·백그라운드 테스트 |
| 본문 선취·재생 | **receive 통과 + ≤64KB 복사**, 상태값 5종, 알려진 필드명만, 7가지 테스트 |
| 미처리 예외마다 500 | `response_started` 추적, 시작 후는 로그만, 취소 구분, 등록 순서·CORS expose 명시 |
| 예외 메시지 유출 | `hide_parameters`, 500자+마스킹, 프레임 위치만, 외부 로거 레벨 |
| 쿼리 블랙리스트 | **화이트리스트 8개**로 전환 |
| Task 7 잠금 | 보호 환경 사용자 필수, 메서드·필드 명시, tz·4h 상한, 200건, 출력 시 재확인, 운영자 id 검증, 감사 실패 시 off, `--sensitive`는 편의 |
| 헤더 신뢰 | 서버 생성 ID, 신뢰 프록시일 때만 `upstream_id`·IP, Amzn은 `trace_id` |
| 보존·Caddy 설명 | 용량 회전 명시, "모든 요청 기록" 명시 |
| Task 6 | 최소 범위로 확정 |
| 검증 | 실제 uvicorn stdout, 고정 순서 |

---

## 구현 기록 (2026-09-22 ~ 23)

rev5 계획대로 Task 1~7 구현. 계획을 쓸 때 몰랐던 것들을 구현 중에 고쳤다.

### 계획에 없던 발견과 수정

1. **Caddy 기본 로거도 요청을 찍는다.** 사이트 블록의 `log` 만 필터하면 `http.log.error` 줄(502 등)에 쿼리·헤더가 그대로 남는다.
   실측으로 `SECRET` 2건이 새는 것을 확인하고 전역 `log default { exclude http.log.access ... }` 에 같은 필터를 걸었다.
   `exclude` 가 없으면 접근 줄이 두 번 찍힌다.
2. **`state` 도 마스킹 대상.** `_SECRET_PAIR` 에 빠져 있어 httpx 가 INFO 로 찍은 URL 에서 `state=` 가 남았다. 패턴에 추가.
3. **`httpx` 가 INFO 로 요청 URL 전체를 찍는다**(`"HTTP Request: GET http://...?code=..."`). `logging_config` 의 WARNING 설정이
   이걸 막는 유일한 방어이므로 테스트로 고정했다(`test_production_logging_config_silences_url_logging_libraries`).
4. **`get_current_user` 시그니처 변경의 여파**: `tests/test_auth_edge_cases.py:515` 가 의존성을 직접 호출한다. `request` 를 넘기도록 수정.
5. **디버그 캡처에 넘기는 본문**: 미들웨어가 `complete and not overflow` 일 때만 복사본을 넘긴다. 불완전·초과분은 값을 찍을 근거가 없다.

### 검증 결과

- `pytest backend/tests`: **1069 passed, 19 skipped**.
- `npm run typecheck` / `build` / `test:mojibake`: PASS.
- **실제 uvicorn stdout 실측**(컨테이너 재빌드 후): 전체 줄이 JSON(비 JSON 0줄), uvicorn access 줄 0건,
  `?token=LEAKTEST999`·`?code=LEAKCODE&state=LEAKSTATE`·`?q=LEAKQ` 호출 후 `LEAK` grep **0건**, 응답 헤더 `x-request-id` 확인.
  `LogConfig` = `json-file max-size=20m max-file=10`.
- **실제 Caddyfile 실측**: `caddy validate` 통과. 토큰 URL·`Referer`·302 `Location` 을 흘린 뒤 `SECRET` grep **0건**,
  접근 줄 중복 없음, `Cf-Connecting-Ip: 198.51.100.77` → `client_ip: 198.51.100.0`, `headers`·`resp_headers` 키 자체가 없음.
- **조회 스크립트 실측**(jq 있는 리눅스 컨테이너): `access-log-summary.sh` 시간대×상태군 표 출력,
  `trace-request.sh <rid>` 해당 요청 줄 출력, `trace-request.sh user:1` 빈 결과.

### known baseline failure — 프런트 vitest 2건

`npm run test`(vitest) 전체 실행에서 2건이 실패한다. **이 브랜치와 무관한 기존 문제다.**
같은 시점에 손대지 않은 루트 develop(`e148b7c`, src 수정 0건)에서 전체 실행해도 같은 2건이 실패한다.

- `home.test.tsx > uses the generic fallback AI trip card ...`
- `trip-create.test.tsx > does not append a late auto-selected travel-area title ...`
  (`travelAreaId` 기대 `busan-all` ↔ 실제 `whole:%EB%B6%80%EC%82%B0` — 메모리 `travel-area-catalog-vs-recommendation-ids` 의 그 문제)

두 파일 모두 `vite.config.ts` 주석대로 **공유 상태 dev 백엔드(login/session)** 를 구동하며, 단독 실행은 통과한다(15/15).
세션 중 날짜가 9/22 → 9/23 로 넘어간 것도 기대값에 영향을 준다. 실행마다 실패 건수가 1~2건으로 흔들린다.

### 로컬 런타임 상태

`travel-hunter-onprem-backend-1` 을 이 워크트리에서 재빌드해 올려 두었다(8000). 프런트는 변경이 작아 기존 4173 빌드 그대로도
동작하지만, "문의 코드" 표시를 보려면 프런트도 재빌드해야 한다.

---

## rev6 — 온프레미스 상시 운영 반영 (2026-09-23)

계획 변경: **온프레미스 환경도 계속 구성·운영한다.** rev3~5는 Caddy 를 "AWS 이전 시 사라질 것"으로 보고 최소 로그만 두었다.
온프레가 1급 환경이면 Caddy 로그는 임시방편이 아니라 **엣지 기록**이고, 백엔드 로그와 **같은 ID 로 이어져야** 쓸모가 있다.

사용자 결정(2026-09-23): ID 는 **채택(하나의 ID)**, Caddy 로그는 **전체 기록 유지**.

### Caddy 능력 실측 (caddy:2-alpine)

| 확인 | 결과 |
|---|---|
| `{http.request.uuid}` | 요청마다 UUID. 접근 로그 최상위 `uuid` 필드에 **필터 없이** 포함된다 |
| `request_header X-Request-Id {http.request.uuid}` | 업스트림이 그대로 받는다 |
| 클라이언트가 보낸 `X-Request-Id` | **덮어쓴다** — 위조 불가 |
| `header ?X-Request-Id` | 정상 응답은 백엔드 값 유지. **502 에는 붙지 않는다** |
| `handle_errors` | 502 에도 헤더 + 본문(`{"detail":…,"requestId":…}`) 을 줄 수 있다 |

### 무엇이 좋아지나

```
rev5:  Caddy(ID 없음) → 백엔드가 자체 생성
       → Caddy 로그와 백엔드 로그를 잇는 값이 없다. 백엔드가 죽으면 사용자는 코드도 못 받는다.

rev6:  Caddy(UUID 생성·기록·전달) → 백엔드가 그 값을 채택
       → 문의 코드 하나로 엣지·백엔드 로그가 동시에 검색된다
       → 백엔드가 죽어도 Caddy 가 같은 형태의 코드를 준다
```

### 변경 (커밋 f380c05 대비 델타)

**Task R1 — `deploy/Caddyfile`, `deploy/Caddyfile.tunnel` (두 사이트 블록 공통)**
```
  request_header X-Request-Id {http.request.uuid}
  header ?X-Request-Id {http.request.uuid}
  handle_errors {
    header X-Request-Id {http.request.uuid}
    respond `{"detail":"Service Unavailable","requestId":"{http.request.uuid}"}` {err.status_code}
  }
```
- `handle_errors` 의 본문은 백엔드의 500 응답과 **같은 형태**다. 프런트 `ApiError` 가 그대로 문의 코드를 집는다.
- 접근 로그는 rev5 그대로(전체 기록 + 필드 화이트리스트). `uuid` 는 기본 포함이라 추가 설정이 없다.

**Task R2 — `app/core/request_context.py`**
- 신뢰 프록시에서 온 `X-Request-Id` 가 형식(`^[A-Za-z0-9._-]{8,64}$`)에 맞으면 **`request_id` 로 채택**한다(rev5 는 `upstream_id` 에만 보관했다).
- 비신뢰 피어의 값은 여전히 무시하고 자체 생성한다. AWS 에서는 ALB 가 이 헤더를 안 붙이므로 자체 생성 경로를 탄다 — **코드 분기 없이 양쪽이 동작한다.**
- 부작용: ID 형식이 환경마다 다르다(온프레 UUID 36자 / 직접·AWS 16진수 16자). 검색에는 영향 없다.

**Task R3 — 테스트**
- 신뢰 피어의 `X-Request-Id` 채택, 비신뢰 피어 무시(기존 유지), 형식 위반 시 자체 생성.
- Caddy 실측: 업스트림 전달, 클라이언트 값 덮어쓰기, 502 의 헤더·본문.

### 온프레 로그의 역할 (rev6 확정)

| 로그 | 무엇을 아는가 |
|---|---|
| Caddy | **모든 요청** — 프런트 자산 포함(백엔드를 안 거친다). 백엔드 사망 시의 502 |
| 백엔드 | 요청의 내부 — 사용자, 예외, 스택, 소요시간 |

둘이 같은 `request_id` 로 묶이므로 "자산은 느린데 API 는 빠르다" 같은 판단이 가능해진다.

### AWS 이전 시 (변함없음)

Caddy 블록은 사라지고 백엔드는 자체 생성 경로로 돈다. `awslogs` 드라이버 교체만 남는다.

### rev6 구현·검증 (2026-09-23)

| 검증 | 결과 |
|---|---|
| `pytest backend/tests` | **1,074 passed** / 19 skipped |
| `caddy validate` (실제 Caddyfile.tunnel) | 통과 |
| **ID 일치 (실측)** | 응답 헤더 · 백엔드 로그 `request_id` · Caddy 로그 `uuid` 가 모두 `915cb0d0-…` 로 같다 |
| **백엔드 사망 시 (실측)** | 502 응답에 `X-Request-Id` + `{"detail":"Service Unavailable","requestId":"54255b66-…"}`, 같은 uuid 가 Caddy 로그에 502 로 기록됨 |

구현 중 확인한 것:
- 로컬 스택(`compose.local.yaml`)은 `TRUSTED_PROXY_CIDRS` 기본값이 비어 있다. Caddy 없이 직결하는 구성이라 맞는 기본값이고,
  이때는 채택 없이 자체 생성한다. **로컬에서 Caddy 를 끼워 확인할 때는 `TRUSTED_PROXY_CIDRS=172.16.0.0/12` 를 준다**(`.env.example` 에 주석).
  배포 스택(`compose.yaml`)은 이 값을 기본으로 넣는다.
- `handle_errors` 없이 `header ?X-Request-Id` 만 두면 502 에는 헤더가 붙지 않는다(실측). 오류 경로를 따로 잡아야 한다.

---

## rev7 — 엣지·앱 로그 합쳐 보기 (2026-09-23)

온프레를 계속 운영하면 로그가 두 컨테이너(`caddy-1`, `backend-1`)에 나뉜다. 분리 자체는 옳다 —
엣지는 프런트 자산 요청과 백엔드 사망 구간을 알고, 앱은 요청 내부를 안다. 불편한 건 **한 요청을 볼 때 두 번 쳐야 하고
시간순으로 섞어 보려면 손으로 맞춰야** 하는 점이다.

사용자 결정(2026-09-23): **A안 — 스크립트가 두 로그를 합쳐 시간순으로 보여 준다.** 수집기 컨테이너는 만들지 않는다.

### 왜 합쳐 보는 게 필요한가

- 프런트 자산 요청은 백엔드 로그에 **아예 없다**. 엣지만 안다.
- 백엔드가 죽은 구간은 **엣지에만** 502 로 남는다.
- "느리다" 신고는 엣지 시간과 앱 시간을 비교해야 원인 구간(프록시냐 앱이냐)이 나온다.

```
12:47:36.180  [edge] GET /api/policies 200  42ms
12:47:36.201  [app]  INFO  app.services.policies  listing 108 policies
12:47:36.233  [app]  ACCESS GET /api/policies 200  31ms  user=42
            → 엣지 42ms, 앱 31ms. 11ms 가 프록시·네트워크 구간.
```

### 왜 수집기 컨테이너를 만들지 않나

Loki 등을 붙이면 컨테이너가 늘고 운영 부담이 생기는데, **AWS 에서는 CloudWatch 가 두 로그를 한 곳에 모으므로
이전 때 통째로 버린다.** 스크립트는 버려도 20줄이고, 합쳐 보는 **조건 자체는 Insights 쿼리로 그대로 옮겨간다**
(로그 그룹 여러 개를 한 쿼리로 조회하는 것은 Insights 기본 기능이다).

### Task S1 — `scripts/trace-request.sh` 확장

- 백엔드 컨테이너와 Caddy 컨테이너의 `docker logs` 를 모아 **`ts` 기준 시간순**으로 출력한다.
- 출처를 `[edge]` / `[app]` 로 표시한다.
- 매칭 기준
  - 앱 줄: `.request_id`
  - 엣지 줄: Caddy 접근 로그의 최상위 `.uuid` (rev6 에서 백엔드가 채택하는 바로 그 값)
- `--app-only` / `--edge-only` 로 한쪽만 볼 수 있다. 기본은 합침.
- Caddy 컨테이너가 없으면(로컬 직결 구성) 조용히 앱 줄만 보여 준다 — 오류가 아니다.
- 컨테이너 이름은 `--container` / `--edge-container` 또는 `TRACE_CONTAINER` / `TRACE_EDGE_CONTAINER` 로 바꾼다.

### Task S2 — `scripts/access-log-summary.sh` 는 그대로

요약은 앱 로그만 본다. 엣지 요약이 필요해지면 그때 더한다.

### 하지 않는 것

- 수집기 컨테이너(Loki·Fluentd 등). 백엔드·Caddy 설정 변경(이번엔 스크립트만 고친다).

### rev7 구현·검증 (2026-09-23)

| 검증 | 결과 |
|---|---|
| 합쳐 보기 | 한 요청의 `[edge]` 줄과 `[app]` 줄이 **시간순으로 함께** 출력됨 |
| `--edge-only` / `--app-only` | 각각 한쪽만. 종료 코드 0 |
| 엣지 컨테이너 없음 | 앱 줄만 조용히 출력. 오류 아님 |
| 백엔드를 안 거친 요청 | `/nope-asset.js` → **엣지 줄만** 나옴(백엔드 로그에 없는 요청) |

구현 중 고친 것:
- **엣지 시각이 UTC 로 나왔다.** Caddy 의 `ts` 는 epoch 이고 컨테이너 TZ 는 UTC 다. 앱 로그가 KST 로 찍으므로
  `+32400` 후 포맷해 같은 축에 올렸다. **정렬 키도 KST ISO 로 맞춰야 한다** — UTC 키와 KST 키를 섞으면 순서가 뒤집힌다.
- `--app-only` 일 때 종료 코드 1. `[ ... ] && 함수` 형태가 `pipefail` 로 새어 나갔다. `if` 문으로 바꿨다.
- 정렬 키 구분자를 원시 제어문자(`\x01`)로 두면 편집기·git 에서 깨진다. **탭으로 바꿨다**(`cut` 의 기본 구분자).

---

## rev8 — 조회 스크립트를 Python 한 파일로 (2026-09-23)

rev4~7 의 조회 스크립트는 bash + jq 였다. **jq 가 실행 환경 어디에도 없다**는 것을 확인하고 Python 으로 옮긴다.

### 실측 근거

| 확인 | PC | 개발서버 |
|---|---|---|
| `jq` | **없음** | **없음** |
| `python3` | 3.12.10 | 3.12.3 |
| `DOCKER_HOST=ssh://dev-server docker logs` | 실제 로그 읽힘 | — |
| 한글 왕복(`docker logs` → Python) | `encoding="utf-8"` 명시 시 무손실, 깨짐 0 | — |

지금 스크립트는 로컬에서도 개발서버에서도 그냥 돌지 않는다(검증할 때마다 jq 가 든 리눅스 컨테이너를 거쳤다).
`scripts/oauth_local_smoke.py` 가 이미 있어 Python 스크립트는 저장소 관례에도 맞는다.

### Task P1 — `scripts/trace.py` (신규, 기존 bash 2개 대체)

```
python scripts/trace.py <request_id | user:42>     # 엣지+앱 합쳐 시간순
python scripts/trace.py <id> --server dev          # 개발서버 (DOCKER_HOST=ssh://dev-server)
python scripts/trace.py --summary --since 24h      # 시간대×상태군, 5xx 상위 경로
python scripts/trace.py --tail                     # 실시간 따라가기
python scripts/trace.py <id> --out trace.txt       # 텍스트로 저장
python scripts/trace.py <id> --app-only | --edge-only | --sensitive
```

- 엣지 줄(Caddy `uuid`)과 앱 줄(`request_id`)을 같은 시간축에 놓는다. Caddy `ts` 는 epoch UTC 이므로 KST 로 맞춘다(rev7 과 동일).
- `--server` 없으면 로컬. `dev` 는 `ssh://dev-server`.
- `subprocess` 인코딩을 `utf-8` 로 명시한다 — Windows 기본(cp949)으로 읽으면 한글이 깨진다.

### 안전 규율 (리뷰 포인트)

- `DOCKER_HOST` 는 **하위 프로세스 env 로만** 넘긴다. 셸에 export 하지 않는다 — 다른 docker 명령이 실수로 원격을 향하면 안 된다.
- 스크립트가 부르는 docker 명령은 **`logs` 와 `inspect` 뿐이다.** `DOCKER_HOST=ssh` 는 원격 Docker API 전체 권한이므로, 조회 계열로 한정하는 것이 유일한 방어다.
- 새 권한을 만들지 않는다. 이미 가진 SSH 접근을 쓸 뿐이고 `docker.sock` 을 어디에도 마운트하지 않는다.

### 삭제

`scripts/trace-request.sh`, `scripts/access-log-summary.sh` — jq 의존이라 실행 불가. 미머지 브랜치라 이력 부담이 없다.

### 그대로

백엔드·Caddy·compose 는 손대지 않는다. **로그 형식은 바뀌지 않는다.**

### rev8 구현·검증 (2026-09-23)

| 검증 | 결과 |
|---|---|
| 합쳐 보기 | 한 요청의 `[edge]` 423ms / `[app]` 417ms 가 시간순으로 — 프록시 구간 6ms 가 드러난다 |
| `--edge-only` / `--app-only` | 각각 한쪽만 |
| 백엔드를 안 거친 요청 | `/asset-only.js` → **엣지 줄만** |
| `--summary` | 시간대×상태군 표 + 5xx 상위 경로 |
| `--out` | 파일 저장 |
| `--tail` | 실시간 출력 |
| **`--server dev`** | 개발서버 컨테이너 조회됨(현재는 브랜치 미배포라 구조화 줄이 없어 "접근 줄 없음") |
| 없는 컨테이너 | 명확한 메시지 + 종료 코드 2 |
| 예외 렌더링 | `↳ 예외타입: 메시지` · 프레임 목록 · `↳ cause ...` · `body_shape` |

삭제: `scripts/trace-request.sh`, `scripts/access-log-summary.sh`.

---

## rev9 — 개발서버 로그 뷰어 (Dozzle) (2026-09-23)

SSH·grep 없이 브라우저로 훑을 창구. 사용자 결정(2026-09-23): **A안 — 개발서버에 두되 `127.0.0.1` 에만 바인딩하고 SSH 터널로 접속.**

역할 분담: **Dozzle 은 훑어보기, `trace.py` 는 특정 요청 파고들기.** 서로 대체하지 않는다.

### 왜 앱이 아니라 별도 뷰어인가

관리자 페이지에 로그 뷰어를 직접 만들려면 백엔드가 자기 로그 파일을 읽어야 하는데, 그러려면 `docker.sock` 마운트
(앱에 서버 root 권한)나 호스트 로그 디렉터리 마운트가 필요하다. **앱 컨테이너에 줄 권한이 아니다.**
게다가 앱이 죽으면 정작 필요한 순간에 로그를 못 본다. 업계에서도 자사 관리자 화면에 로그 뷰어를 직접 만드는 경우는 드물다.

### 실측 (amir20/dozzle:latest)

| 확인 | 결과 |
|---|---|
| 이미지 크기 | **20.0 MB** |
| 기동·응답 | 읽기 전용 소켓 마운트로 HTTP 200, 권한 오류 없음 |
| 로그 저장 | **하지 않는다** — Docker 가 이미 가진 것을 읽어 보여 줄 뿐 |
| `--filter` | 컨테이너를 Docker 문법으로 제한 가능 |
| `--auth-provider` | none / simple / oidc / forward-proxy |
| compose `profiles` | **기본 `up -d` 에서 제외됨**(실측: `always` 만 뜨고 `optional` 은 안 뜸) |

### Task D1 — `compose.yaml` 에 프로필로 추가

```yaml
  dozzle:
    image: amir20/dozzle:latest
    profiles: ["logs"]                     # 기본 up 에서 제외 - Jenkins 배포가 건드리지 않는다
    command: ["--filter", "name=travel-hunter-onprem"]
    environment:
      DOZZLE_NO_ANALYTICS: "true"
    ports:
      - "127.0.0.1:8888:8080"              # 루프백 전용. 공개 면을 만들지 않는다
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped
    logging: { driver: json-file, options: { max-size: "20m", max-file: "10" } }
```

- **프로필**: Jenkins 의 `docker compose up -d --wait` 는 프로필 서비스를 올리지 않는다(실측). 운영 서버에 저절로 생기지 않는다.
- **`127.0.0.1` 바인딩**: Cloudflare 터널·Caddy 어디에도 걸리지 않는다. 외부에서 도달 불가.
- **`--filter`**: 우리 스택 컨테이너만 보인다. Jenkins 등 다른 컨테이너 로그는 안 보여 준다.
- **읽기 전용 소켓**: `:ro`. 다만 Docker API 자체가 강력하므로 루프백 바인딩이 실질적 방어다.
- 인증을 걸지 않는 이유: 도달하려면 개발서버 SSH 접근이 필요하고, 그 사람은 `docker logs` 를 이미 쓸 수 있다. 권한이 늘지 않는다.

### 사용법

```
ssh -L 8888:127.0.0.1:8888 dev-server      # 터널을 연 채로 두고
# 브라우저에서 http://127.0.0.1:8888
```

기동/정지(개발서버에서 한 번):
```
docker compose -p travel-hunter-onprem --env-file <env> -f compose.yaml --profile logs up -d dozzle
docker compose -p travel-hunter-onprem --profile logs stop dozzle
```

### 하지 않는 것

- 운영 서버 적용(별도 승인). 공개 도메인 노출. 인증 연동(OIDC 등).
- 로그 저장·수집. Dozzle 은 저장하지 않는다 — 보존은 Docker 회전 설정이 계속 맡는다.
- 로컬 PC 스택에는 넣지 않는다. Docker Desktop 에 이미 로그 화면이 있다.

### AWS 이전 시

Dozzle 은 삭제한다. CloudWatch Logs Insights 가 같은 역할을 한다.

### rev9 구현·검증 (2026-09-23)

| 검증 | 결과 |
|---|---|
| `compose config --services` | 기본: db·backend·frontend·caddy·cloudflared (**dozzle 없음**) |
| `--profile logs` | 위 5개 + **dozzle** |
| 기동 | 읽기 전용 소켓으로 HTTP 200, 로그에 오류 0 |
| **`--filter` 실효** | 필터 없음 **13개** → 필터 있음 **3개**(우리 스택만). `tosstock-bot`·`travel-hunter-region-photos-*` 등은 보이지 않는다 |
| 포트 바인딩 | `8080/tcp -> 127.0.0.1:18101` — 루프백 전용 확인 |
| 이미지 | 20.0 MB, 로그 저장 없음 |

`--filter name=travel-hunter-onprem` 은 부분 일치다. `travel-hunter-region-photos-*` 는 문자열이 달라 제외된다(실측 확인).

---

## rev10 — `--recent` (활동 전체를 시간순으로) (2026-09-23)

`--tail --since 24h` 로도 이력이 나오지만 두 가지가 불편하다.

- **끝나지 않는다.** 이력만 보고 싶어도 `Ctrl+C` 를 눌러야 한다.
- **엣지 줄이 안 섞인다.** `--tail` 은 앱 로그만 따라간다. 화면·자산 요청과 백엔드 사망 구간은 Caddy 에만 있으므로
  "화면이 안 떠요" 류의 신고를 이 모드로는 못 본다.

사용자 요청(2026-09-23): **이력만 보고 끝나며 엣지 줄도 섞어 주는 모드**를 추가한다.

### Task R1 — `scripts/trace.py --recent`

- 기간 안의 **모든 줄**을 엣지·앱 합쳐 시간순으로 출력하고 끝낸다(follow 하지 않는다).
- 키(`request_id` / `user:<id>`)를 요구하지 않는다.
- 기존 옵션과 조합된다: `--since` · `--server` · `--app-only` / `--edge-only` · `--out` · `--sensitive`.
- 구현은 키 기반 경로를 재사용한다 — 선택자를 "항상 참", 엣지 키를 `None`(전체)으로 둔다.

### 모드 정리

| 모드 | 무엇 | 끝나는가 | 엣지 포함 |
|---|---|---|---|
| `<코드>` | 한 요청 | 예 | 예 |
| `--recent` | 기간 내 전체 활동 | **예** | **예** |
| `--summary` | 통계 표 | 예 | 아니오(앱 기준) |
| `--tail` | 실시간 | 아니오 | 아니오 |

### 하지 않는 것

출력 건수 상한. `--since` 로 조절하고 많으면 `--out` 으로 저장한다.

### rev10 구현·검증 (2026-09-23)

| 검증 | 결과 |
|---|---|
| `--recent` | 기간 내 전체가 시간순으로 출력되고 **종료된다** |
| 엣지 섞임 | `[edge]`/`[app]` 가 한 축에. `/static-asset.css` 는 **엣지에만** 나온다(백엔드를 안 거치는 요청) |
| `--edge-only` 조합 | 엣지 줄만 |
| `--out` 조합 | 파일 저장 |
| 키 없이 실행 | 안내 문구에 `--recent` 포함 |

구현은 키 기반 경로를 재사용한다 — 선택자를 항상 참, 엣지 키를 `None`(전체)으로 둔다. 새 읽기 경로를 만들지 않았다.

---

## rev11 — 로그를 컨테이너 수명에서 분리 (2026-09-23)

**문제**: 배포할 때마다 로그가 사라진다. `docker logs` 가 읽는 파일은 `/var/lib/docker/containers/<컨테이너ID>/…` 에 있고
**컨테이너 ID 가 경로의 일부**라, `docker compose up -d` 로 컨테이너가 재생성되면 이전 파일이 함께 삭제된다.
개발서버는 배포가 잦아 실질 보존 기간이 "마지막 배포 이후"다 — 200MB 한도보다 이게 먼저 걸린다.

사용자 결정(2026-09-23): **항상 남아야 한다.**

### 실측

| 확인 | 결과 |
|---|---|
| 로그 드라이버를 `local` 로 바꾸면? | **소용없다.** 재생성 전 줄이 사라진다(`BEFORE-RECREATE` 소실 확인). 드라이버와 무관하게 컨테이너 ID 에 묶인다 |
| 이름 있는 볼륨은 재생성을 견디나 | **견딘다.** 컨테이너를 지우고 새로 만들어도 파일이 그대로 |
| Caddy 가 stdout 과 파일에 동시에? | **불가.** 이름 있는 `log` 두 개를 둬도 **파일에만** 기록된다(stdout 0건) |

### 설계

앱이 **직접 파일로도 쓴다.** 저장 위치는 이름 있는 볼륨이라 컨테이너 수명과 무관하다.

```
backend ─┬─ stdout ──→ docker json-file (최근 것, docker logs·Dozzle 용)
         └─ 파일   ──→ 볼륨 travelhunter-logs/backend.log   (영구 이력)
caddy   ─── 파일   ──→ 볼륨 travelhunter-logs/caddy-access.log
```

- 백엔드는 **둘 다** 쓴다(Python 은 핸들러를 두 개 붙이면 된다). `docker logs`·Dozzle 의 편의를 잃지 않는다.
- Caddy 는 동시 출력이 안 되므로 **파일만** 쓴다. Caddy 의 기동·오류 줄은 기본 로거를 통해 stdout 에 계속 남는다.
- 회전은 앱이 한다: Python `RotatingFileHandler`(20MB × 10), Caddy `roll_size`/`roll_keep`.
- **읽기는 `docker exec <컨테이너> cat`** 으로 한다. `DOCKER_HOST=ssh` 를 그대로 타므로 로컬·개발서버가 같은 방식이고,
  호스트 파일 권한(root 소유)을 건드릴 필요가 없다.

### Task L1 — 백엔드 파일 핸들러

`app/core/logging.py` 에 `RotatingFileHandler` 추가. 경로·용량은 설정으로(`LOG_FILE_PATH`, 기본 `/var/log/travelhunter/backend.log`).
경로가 비었거나 쓸 수 없으면 **stdout 만 쓰고 조용히 넘어간다** — 로깅 설정 실패로 앱이 못 뜨면 안 된다.

### Task L2 — Caddy 파일 출력

`deploy/Caddyfile` ×2 의 `accesslog` snippet 을 `output stdout` → `output file /var/log/travelhunter/caddy-access.log { roll_size 20mb  roll_keep 10  roll_uncompressed }` 로.
필터(쿼리 제거·헤더 삭제·IP 마스킹)는 그대로 둔다.

### Task L3 — compose

이름 있는 볼륨 `travelhunter-logs` 를 backend(rw)·caddy(rw) 에 `/var/log/travelhunter` 로 마운트.

### Task L4 — `scripts/trace.py` 가 파일을 읽는다

- 기본 조회(`<코드>`·`--recent`·`--summary`)는 **볼륨 파일**을 읽는다 — 배포를 넘어선 이력이 나온다.
- `docker exec` 로 읽되 backend → caddy 순으로 시도한다(백엔드가 죽어 있으면 caddy 로).
- `--tail` 은 지금처럼 `docker logs --follow` 를 쓴다(실시간).
- `--source docker` 로 예전 방식(컨테이너 로그)을 강제할 수 있게 둔다.
- 안전 규율 갱신: 부르는 docker 명령에 **`exec … cat <고정 경로>`** 가 추가된다. 인자가 고정이고 읽기 전용이다.

### 하지 않는 것

- 호스트 디렉터리 바인드 마운트(권한·플랫폼 문제). 로그 수집기 컨테이너. syslog 드라이버.
- `docker logs` 경로 제거 — 최근 것은 계속 그쪽이 빠르다.

### rev11 구현·검증 (2026-09-23)

**재배포 생존 실측** — 마커 요청을 남기고 `up -d --force-recreate` 로 컨테이너를 재생성했다.

| | 재생성 전 | 재생성 후 |
|---|---|---|
| `docker logs` 에 마커 | 1건 | **0건 (사라짐)** |
| 볼륨 파일에 마커 | 1건 | **1건 (남음)** |
| 볼륨 파일 줄 수 | 13 | **21 (누적)** |

| 검증 | 결과 |
|---|---|
| `trace.py --recent` 기본 | 재배포 **이전** 줄(16:28~16:45)부터 출력 |
| `--source docker` | 재생성 **이후**(16:46~)만 출력 — 두 조회원이 실제로 다르다 |
| 재배포 전 요청을 코드로 조회 | 나온다 |
| 백엔드 stdout 병행 | 마커가 파일·컨테이너 로그 양쪽에 있었다(재생성 전) |
| `pytest backend/tests` | 1,074 passed / 19 skipped |
| `caddy validate` · `compose config` | 통과 |

**환경 문제 하나(코드와 무관)**: 검증 중 호스트에서 `127.0.0.1:8000` 이 응답하지 않았다.
VS Code(PID 56984)가 그 주소를 선점해 Docker 는 `::`(IPv6)에만 바인딩된 상태였다. `http://[::1]:8000` 으로는 정상이다.
컨테이너 내부 헬스체크는 계속 통과했다.

---

## rev12 — 코덱스 리뷰 반영 (2026-09-28)

재부팅으로 스택이 내려갔다가 복구했다. **볼륨 로그는 재부팅을 넘어 살아남았다** — 9/23 마커가 파일에 그대로 있고
`docker logs` 에는 없다(31줄, 9/23~9/28). rev11 의 목적이 재배포뿐 아니라 전원 차단에도 성립한다.

코덱스가 실제 코드에서 찾은 결함 3건과 보완 5건을 반영한다.

### 결함 3건

**① `--since` 가 볼륨 조회에 적용되지 않았다.** 파일 전체가 출력됐다.
→ `parse_since()` 로 기준 시각을 만들고 레코드의 `ts` 로 거른다. `--recent` · `--summary` · 키 조회 모두 같은 기준.
앱 줄은 ISO 문자열, 엣지 줄은 epoch 초라 `record_time()` 이 둘을 흡수한다.

**② Caddy 회전 파일을 못 읽었다.** 코드는 `caddy-access.log.*` 를 찾았지만 실제 이름은 다르다.
실측으로 확인한 형식: `caddy-access-2026-09-28T03-56-10.890-size.log` (lumberjack: `<이름>-<UTC 타임스탬프>-<사유>.<확장자>`).
→ 디렉터리를 훑어 `backend.log.N` 과 `caddy-access-*.log[.gz]` 를 모두 잡고, `.gz` 는 `gzip -dc` 로 읽는다.
정렬은 `_rotation_order()` 가 맡는다 — 백엔드는 **숫자 역순**(`.10` 이 `.1` 보다 오래됐다. 문자열 정렬이면 `.10` 이 `.2` 앞에 온다),
Caddy 는 이름의 타임스탬프순, 현재 파일이 마지막.

**③ `docker exec` 가 실패해도 빈 결과로 exit 0 이었다.** 권한 오류·컨테이너 정지를 "로그 없음"으로 오해한다.
→ 모든 컨테이너에서 실패하면 `LogReadError` 로 stderr 에 원인을 내고 **종료 코드 3**.
"파일이 없다"(정상 0건)와 "읽지 못했다"(오류)를 구분한다.

### 보완 5건

- **읽기 상한**: `--max-mb`(기본 64MB). 넘으면 `tail -c` 로 최근 쪽만 읽고 잘린 첫 줄을 버린 뒤 알림을 낸다.
- **`down -v` 경고**: 아래 운영 규칙 절에 기록.
- **파일 쓰기 실패 경고**: 파일을 열 수 없으면 stdout 에 `WARNING` 한 줄을 내고 stdout 전용으로 계속한다. 조용히 넘어가지 않는다.
- **`.10` 이상 정렬**: 위 `_rotation_order()`.
- **Dozzle 한계**: 아래 운영 규칙 절에 기록.

### 운영 규칙 (중요)

| 항목 | 내용 |
|---|---|
| **`docker compose down -v` 금지** | `-v` 는 `travelhunter-logs` 볼륨을 DB 볼륨과 함께 지운다. **로그 이력이 사라진다.** 운영·개발서버에서는 `down` 만 쓴다. 볼륨을 정말 지워야 하면 `docker volume rm` 으로 대상을 명시한다 |
| **Caddy 접근 로그는 `docker logs` 에 없다** | Caddy 는 접근 로그를 한 곳에만 쓸 수 있어(실측) 파일로 보낸다. 따라서 **Dozzle 과 `docker logs caddy` 에는 기동·오류 줄만 보인다.** 엣지 접근 기록은 `trace.py` 로 본다 |
| **파일 열기 실패(기동 시)** | `WARNING` 한 줄을 남기고 stdout 전용으로 계속한다. 이 경고가 보이면 볼륨 마운트·권한을 확인한다 |
| **실행 중 쓰기 실패(디스크 참 등)** | Python 표준 `--- Logging error ---` 가 stderr 로 나온다. stdout 핸들러는 별개라 계속 기록된다. 자동 전환은 없다 |
| **기본 조회 기간** | `--since` 기본 48h. 오래된 이력은 `--since 30d` 처럼 늘린다 |

### rev12 검증 (2026-09-28)

| 항목 | 결과 |
|---|---|
| 재부팅 후 볼륨 로그 보존 | **통과** — 9/23 마커가 파일에 1건, `docker logs` 에 0건 |
| `--since` 적용 | `--since 30d` 33줄 ↔ `--since 1h` 5줄. `--summary` 도 동일 |
| Caddy 회전 파일 읽기 | 실제 형식(`caddy-access-2026-09-28T01-00-00.000-size.log`) 1건 포함 확인 |
| `docker exec` 실패 | **exit 3** + stderr 에 컨테이너별 원인. "파일 없음"은 여전히 정상 0건 |
| 파일 열기 실패 | stdout 에 `WARNING` 한 줄 후 stdout 전용으로 계속 |
| 회전 정렬 | 백엔드 `.10 → .9 → .2 → .1 → 현재`, Caddy 타임스탬프순 |
| 로그 테스트 | 61 passed |
| 전체 `pytest` | **1,074 passed** / 19 skipped |
| `caddy validate` | Caddyfile · Caddyfile.tunnel 모두 통과 |
| `compose config` | compose.yaml · compose.local.yaml 모두 통과 |
| `git diff --check` | clean |

### rev12 보강 — trace.py 자동 회귀 테스트 (2026-09-28)

앞서 보고한 61건은 백엔드 로깅 테스트였고 **`trace.py` 자체에는 자동 테스트가 없었다**(코덱스 지적).
`backend/tests/test_trace_script.py` 를 추가한다 — Docker 없이 돌도록 `subprocess.run` 을 가짜로 바꿔
파일 목록·내용·실패를 흉내 낸다.

**고정하는 동작 23건**

| 묶음 | 내용 |
|---|---|
| `parse_since` | `90s` `30m` `2h` `7d` **`1h30m`** `48h` · ISO(오프셋 유·무) · 잘못된 입력은 `LogReadError` · 빈 값은 필터 없음 |
| `record_time` | 앱 줄 ISO 문자열 · 엣지 줄 epoch · 깨진 값은 None |
| 회전 정렬 | 백엔드 `.10 → .9 → .2 → .1 → 현재`(문자열 정렬이면 틀린다) · Caddy 타임스탬프순, 현재 파일 마지막 |
| 파일 탐색 | **실제 Caddy 회전 파일명**과 `.gz` 인식 · 다른 stem·비로그 파일 배제 · 실패를 빈 목록이 아니라 사유로 |
| 읽기 | `.gz` 는 `gzip -dc` · 오래된 것부터 · 전 컨테이너 실패 시 예외(컨테이너별 사유 포함) · 두 번째 컨테이너로 폴백 · **파일 없음은 오류 아님** |
| 읽기 상한 | `tail -c` 적용 · **잘린 첫 줄 폐기** · 알림 출력 |
| `--since` | 앱·엣지 행 모두 거름 · 없으면 전부 통과 · `--summary` 도 같은 기준 |
| 민감 | `kind=debug` 는 `--sensitive` 없이는 안 나온다 |

**변이 테스트로 실효성 확인** — 고친 결함 3건을 하나씩 코드에 다시 심어 해당 테스트가 실패하는지 봤다.

| 되돌린 결함 | 실패한 테스트 |
|---|---|
| `--since` 무시 | `test_cutoff_filters_app_and_edge_rows` |
| Caddy 회전 패턴을 `.log.*` 로 | `test_list_rotated_matches_real_caddy_names_and_gz` |
| 전부 실패해도 조용히 빈 결과 | `test_read_volume_file_raises_when_every_container_fails` |

셋 다 잡았고, 원복 후 23건 전부 통과한다.

### rev12 최종 검증 (2026-09-28)

| 항목 | 결과 |
|---|---|
| `trace.py` 테스트 | **23 passed** (신규) |
| 전체 `pytest` | **1,097 passed** / 19 skipped |
| `caddy validate` | Caddyfile · Caddyfile.tunnel 통과 |
| `compose config` | compose.yaml · compose.local.yaml 통과 |
| `git diff --check` | clean |

---

## rev13 — 훑어볼 때의 가독성 (색·정렬) (2026-09-28)

적재 형식은 JSON 한 줄이다. 기계가 검색·필터하기 위한 형식이고(CloudWatch 가 필드를 자동 인식하는 이유도 이것),
**사람이 읽기 좋게 만드는 일은 도구가 맡는다.** 지금 `trace.py` 출력은 정상 요청과 오류가 같은 밀도로 흘러
눈에 띄지 않는다. 색과 정렬만 손본다(요청 묶기·필터링은 하지 않는다).

### Task V1 — 색

- 상태코드: 5xx 빨강 · 4xx 노랑 · 2xx/3xx 기본 · `ERROR` 줄 빨강 · `WARNING` 노랑
- 출처 표시: `[edge]` 와 `[app]` 을 다른 색으로
- 시각·`rid` 는 흐리게(dim) — 본문이 먼저 읽히게
- **터미널이 아닐 때(파이프·`--out`)는 색을 끈다.** `--color always|auto|never` 로 강제할 수 있다.
  `NO_COLOR` 환경변수도 존중한다.

### Task V2 — 정렬

- 열 폭을 맞춰 표처럼 읽히게: 시각 · 출처 · 종류 · 상태 · 소요시간 · 경로 순
- **UUID 는 앞 8자만** 보여 준다(전체는 `--full-id`). 36자 UUID 가 줄의 절반을 먹고 있었다
- 소요시간은 오른쪽 정렬(`tabular` 느낌)로 크기 비교가 되게

### 하지 않는 것

요청 묶기(같은 request_id 들여쓰기) · `--errors-only` · Dozzle 출력 가공. 별도 작업으로 남긴다.

### rev13 구현·검증 (2026-09-28)

**전**
```
14:00:42      [edge] GET /api/policies 200  423ms  net=172.19.0.0
14:02:11.412  [app]  ACCESS POST /api/trips/17/policies 500  1312ms  user=42  rid=1652b049-...-4c8f
```
**후**
```
14:02:11      [edge]          200   423ms  GET /api/policies  net=172.19.0.0
14:02:11.412  [app]  ACCESS   200   417ms  GET /api/policies  user=42 rid=cc772b50
14:02:11.412  [app]  ACCESS   404    33ms  GET /api/policies/nope  user=- rid=7374694c
14:02:11.412  [app]  ACCESS   500  1312ms  POST /api/trips/17/policies  user=42 rid=1652b049
                   body_shape={"policyId": "int"}
14:02:11.412  [app]  ERROR  app.services.trips  정책 연결 실패
                   ↳ IntegrityError: UNIQUE constraint failed
                     app/services/trips.py:210:link_policy
```

상태·소요시간이 고정 열에 오고 소요시간은 오른쪽 정렬이라 `1312ms` 가 눈에 띈다. UUID 는 앞 8자만(`--full-id` 로 전체).

| 검증 | 결과 |
|---|---|
| 열 정렬 | 엣지·앱 줄의 상태 열이 같은 자리, 소요시간은 끝나는 열이 같다(테스트로 고정) |
| 색 | 5xx 빨강+굵게 · 4xx 노랑 · ERROR 빨강 · WARNING 노랑 · 시각/rid 흐리게 |
| 색 끄기 | 파이프·`--out` 에서 ANSI **0건**. `NO_COLOR` 가 `--color always` 보다 우선 |
| `trace.py` 테스트 | **38 passed** (23 + 색·정렬 15) |
| 전체 `pytest` | **1,112 passed** / 19 skipped |
| `caddy validate` · `compose config` · `git diff --check` | 모두 통과 |

색 코드가 들어가면 `len()` 이 늘어 열이 어긋나므로, `_source_tag()` 가 **폭을 먼저 맞추고 칠한다**.

---

## rev14 — 명령 짧게 (래퍼 + 기본값) (2026-09-28)

`python scripts/trace.py --recent --since 7d --server dev` 는 길다. 거슬리는 건 `python scripts/` 반복과
`--server dev` 반복이다. 하위 명령 구조(`trace recent`)로 재편하는 방법도 있지만 이득이 작고 문서·안내문을 전부 고쳐야 해서
**래퍼와 기본값만** 손본다.

### Task C1 — 래퍼

`scripts/trace.cmd`(Windows) · `scripts/trace`(bash) 두 줄짜리. 인자를 그대로 `python scripts/trace.py` 로 넘긴다.
저장소 안에 있으므로 `cd` 는 남는다 — PATH 등록은 각자 PC 설정이라 안내문에 적는다.

### Task C2 — 짧은 형태

- `--dev` / `--prod` : `--server dev|prod` 의 짧은 형태
- `--stats` : `--summary` 의 별칭(기존 이름도 계속 받는다)
- **`TRACE_SERVER` 환경변수**: 기본 대상 서버. 옵션이 있으면 옵션이 이긴다

```
trace 413dba2b               # 문의 코드
trace --recent --since 7d    # 활동 전체
trace --stats                # 요약
trace --dev --recent         # 개발서버
```

### 하지 않는 것

하위 명령 구조 재편. PATH 자동 등록.

### rev14 구현·검증 (2026-09-28)

```
전: python scripts/trace.py --recent --since 7d --server dev
후: trace --recent --since 7d --dev        (TRACE_SERVER=dev 면 --dev 도 생략)
```

| 검증 | 결과 |
|---|---|
| `--dev` / `--prod` | `--server dev|prod` 와 같은 결과 |
| `--stats` | `--summary` 별칭. 기존 이름도 계속 받는다 |
| `TRACE_SERVER` | 기본 대상으로 쓰이고, 옵션이 있으면 **옵션이 이긴다** |
| bash 래퍼 | 인자·`--help` 를 그대로 넘긴다. 실행 권한 `100755` 로 기록 |
| cmd 래퍼 | 동작 확인 |
| `trace.py` 테스트 | **42 passed** (38 + 짧은 형태 4) |
| 전체 `pytest` | **1,116 passed** / 19 skipped |
| `caddy validate` · `compose config` · `git diff --check` | 통과 |

구현 중 걸린 것:
- **`.cmd` 는 CRLF 가 아니면 `REM` 줄이 명령으로 샌다.** LF 로 저장했더니 `'짧은'은(는) 내부 또는 외부 명령...` 오류가 먼저 났다.
  CRLF + ASCII 주석으로 다시 쓰고, git 이 정규화하지 못하게 `.gitattributes` 에 `*.cmd text eol=crlf` 를 넣었다.
- 인자 해석을 테스트하려고 `build_parser()` 를 `main()` 에서 분리했다.

**개발서버 조회는 이번에 확인하지 못했다** — `ssh dev-server` 가 네트워크에서 응답하지 않는다(연결 시간 초과).
`--dev` 플래그가 대상을 dev 로 바꾸는 것까지는 확인했다(오류 메시지에 "dev 서버의" 표시). 네트워크 복구 후 재확인이 필요하다.

---

## rev15 — 재검토 결함 수정 (2026-09-28)

커밋(`22551ed`) 후 푸시 전에 다시 검토했다. 푸시 전 필수 3건, AGENTS.md 위반 2건, 개선 3건을 고치고 커밋을 보정한다.

### 필수

| 결함 | 실증 | 수정 |
|---|---|---|
| `trace.py` 가 Python 3.11 에서 파싱 불가 | `SyntaxError: f-string: expecting '}'` (python:3.11) — f-string 안에서 바깥과 같은 따옴표 재사용은 3.12 전용(PEP 701) | 값을 먼저 만들고 `rjust`. 3.11 에서 `--help` 실행 확인 |
| 호스트 실행 시 `C:\var\log\travelhunter\` 생성 | Windows 에서 `/var/log/...` 가 C 드라이브 루트로 풀린다(실측). e2e 러너·호스트 pytest 가 `app.main` 을 import 하면 생긴다 | 코드 기본값을 빈 값(비활성)으로. 경로는 compose 가 컨테이너에만 준다(배포 스택 전달 확인) |
| 회전 파일명 정규식이 따옴표를 받음 | `caddy-access-x'; rm -rf / #.log` 매치 → `sh -c '…'` 인용이 깨진다 | 허용 문자를 `[A-Za-z0-9._-]` 로. **`ls` 출력을 `split()` 이 아니라 `splitlines()` 로** 읽는다 — 공백 분리가 이상한 이름을 우연히 쪼개 걸러 주고 있어 정규식이 방어선 역할을 못 하고 있었다 |

### AGENTS.md

- `.env.example` 에 `LOG_FILE_PATH` · `LOG_FILE_MAX_MB` · `LOG_FILE_BACKUPS` 를 설명과 함께 추가했다.
- `CHECKLIST.md` 의 현재 상태·검증·위험을 이 브랜치 기준으로 교체했다. PR #81·#82 도 갱신하지 않았던 기존 누락을 함께 메운다.
  교체 구간에 있던 제어문자 손상(`\a` 가 `admin` 의 `a` 를, 탭이 `test` 의 `t` 를 먹은 것)도 사라졌다.

### 개선

- bash 래퍼: `python3` 만 부르면 Windows 스토어 스텁(WindowsApps)에 걸릴 수 있다. `python3`·`python` 중 3.10 이상으로 실제 돌아가는 쪽을 고른다.
- `parse_since` 의 이중 컴프리헨션을 `timedelta` 합으로.
- 테스트 헬퍼의 안 쓰는 인자 제거.

### 문서 정정

rev12 에 "파일 쓰기·회전 실패 시 stdout fallback 및 경고"라고 적은 것은 과장이었다. 내가 만든 `WARNING` 은 **기동 시 열기 실패**만이다.
실행 중 쓰기 실패는 Python 표준 `--- Logging error ---` 가 stderr 로 나오고 stdout 핸들러는 계속 동작한다. 운영 규칙 표를 고쳤다.

### 가드 테스트와 변이 확인

| 가드 | 변이(옛 코드 재주입) 시 |
|---|---|
| 3.12 전용 f-string 검사(토큰 단위) | 실패 — `ast.parse(feature_version=(3, 11))` 로는 못 잡아서(실측) 토크나이저로 직접 본다 |
| 셸 문자 파일명 4종 | **4건 모두 실패** (`splitlines` 전환 전에는 2건만 실패했다) |
| 파일 로그 기본 비활성 | `Settings` 기본값과 빈 경로의 핸들러 구성 확인 |

### 검증

| 항목 | 결과 |
|---|---|
| 전체 `pytest` | **1,122 passed** / 19 skipped |
| 로그 관련 | 109 passed (trace.py 47 · 요청 로그 35 · 디버그 캡처 27) |
| Python 3.11 | 파싱·`--help` 실행 OK |
| `caddy validate` ×2 · `compose config` ×2 | 통과 |
| 래퍼 bash·cmd | 동작 |
| 변경 파일 U+FFFD·제어문자 | 0건 |
| `git diff --check` | clean |

### 남은 위험

- `RotatingFileHandler` 는 다중 프로세스 안전하지 않다(현재 워커 1개).
- 개발서버 `--dev` 실동작 미확인(SSH 시간 초과).
- 프런트 vitest 2건은 develop 기존 실패.

---

## rev16 — 최종 HEAD 리뷰 결함 수정 (2026-09-28)

PR 전 게이트에서 최종 HEAD(`942c3a9`)를 독립 리뷰했다. HIGH 는 없고 MEDIUM 2건이 나왔다.
1번은 "읽기 실패는 종료 코드 3" 약속을 깨므로 PR 전에 고친다.

| # | 결함 | 수정 | 가드 테스트 |
|---|---|---|---|
| M1 | `ls -1 … 2>/dev/null` 이 실패 메시지를 버려, 종료 코드가 0 이 아니어도 오류 문자열이 비어 "로그 없음"으로 끝났다. 두 번째 컨테이너도 시도하지 않았다. 볼륨이 없는 옛 배포본에서 그대로 재현된다 | 리다이렉트 제거. 메시지가 비면 `exit <코드>` 를 원인으로 쓴다(본문 읽기도 같게) | 종료 코드 2 + 빈 stderr → 다음 컨테이너 시도, 전부 실패 시 `LogReadError` |
| M2 | `splitlines()` 는 U+2028·U+2029·U+0085 에서도 줄을 나눈다. `json.dumps(ensure_ascii=False)` 는 이 문자를 이스케이프하지 않고, `path` 는 퍼센트 디코딩된 값이라 `/%E2%80%A8x` 요청이 두 조각으로 쪼개져 조회에서 사라진다(파일 원본은 온전) | 로그 본문은 `split("\n")`. `ls` 목록도 같게 | U+2028 이 든 줄이 한 레코드로 남는다 |
| L3 | `--source docker` 도움말이 엣지 줄도 나오는 것처럼 읽힌다 | Caddy 접근 줄은 볼륨에만 있다고 명시 | — |
| L5 | 정규식은 `strip()` 한 이름을 검사하고 경로에는 원래 이름을 썼다 | 공백 뗀 이름 하나로 통일 | — |
| L6 | `--stats` 만 `ts` 를 못 읽은 레코드를 기간 안으로 넣었다 | 다른 모드처럼 버린다 | 깨진 `ts` 레코드가 요약에서 빠진다 |
| L8 | 잘린 첫 줄 버리기 테스트가 원래 깨진 JSON 을 써서, 버리지 않아도 통과했다 | 잘린 첫 줄을 올바른 JSON 으로 | 버리기를 되돌리면 실패 |

미룬 것(남은 위험으로 기록):

- L4 파이프라인에 `pipefail` 이 없어 `ls` 와 `cat` 사이에 회전이 일어나면 그 파일을 건너뛰거나 두 번 읽을 수 있다. 백엔드 이미지의 `sh`(dash)는 `pipefail` 을 지원하지 않아 방식을 따로 설계해야 하고 증상이 일시적이다.
- L7 `LOG_FILE_MAX_MB=0` 이면 회전하지 않는다(`maxBytes=0`). 운영자 설정 실수에만 해당한다.

순서: 수정 → 변이 확인 → 전체 게이트 → 커밋 보정 → 새 HEAD 로 재리뷰 → 푸시·Draft PR.

### 결과

| 항목 | 결과 |
|---|---|
| 변이: 빈 실패 메시지 / `splitlines` 복귀 / 요약 `or cutoff` / 첫 줄 버리기 제거 | 4건 모두 해당 테스트 실패 |
| 전체 `pytest`(Linux 백엔드 이미지) | 1,125 passed / 19 skipped |
| 로그 관련 | 112 passed (trace.py 50 · 요청 로그 35 · 디버그 캡처 27) |
| Windows 호스트 venv | 스냅숏 권한 테스트 1건 실패 — develop 에서도 동일(임시 폴더 ACL) |
| Python 3.11 `--help` · bash 래퍼 · `git diff --check` · UTF-8 | 통과 |
