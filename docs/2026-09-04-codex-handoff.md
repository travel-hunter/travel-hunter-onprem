# Codex 인계 — 네 세션 밖에서 바뀐 것

작성: 2026-09-04 09:33 KST / 작성자: Claude 세션
기준: `HEAD = d0f77a8`, 브랜치 `feature/itinerary-day-strip`

너와 같은 체크아웃에서 다른 세션이 동시에 작업했다.
**네 기준선(baseline)이 네가 모르는 사이에 바뀌었다.** 그것부터 읽어라.

---

## 1. 가장 중요 — `.env` 를 고쳤다. 네 기준선이 이동했다

### 무엇을

`TRAVEL_HUNTER_PUBLIC_BASE_URL` 을 `4173` → `5173` 으로 바꿨다. 세 파일이다.

```
.env:13                 (docker compose 용)
backend/.env:21
backend/.env.local:1    ← 실효값. 아래 설명
```

`CORS_ORIGINS` 는 안 건드렸다. 5173 이 이미 들어 있었고 4173 도 남겨 뒀다.
`.env.local` 의 OAuth 리다이렉트 URI 들은 제공자에 등록된 값이라 손대지 않았다.

세 파일 다 저장소 밖에 `chmod 600` 으로 백업했다.

### 왜 — 네가 "환경성 실패"라고 적었던 6건의 정체

네 CHECKLIST 에 `682 passed / 6 failed` 를 환경 문제로 넘겼는데, **5건은 이 포트 하나였다.**

```
기대  http://127.0.0.1:5173/oauth/callback?...
실제  http://127.0.0.1:4173/oauth/callback?...
```

- `test_auth_db_routes.py` 4건
- `test_trip_db_service.py::test_invite_to_api_computes_display_flags`

나머지 1건 `test_stay_discount_semantics_snapshot.py::test_restricted_atomic_artifact_and_sidecar_round_trip`
은 Windows 임시 디렉터리 권한 문제이고 **간헐적이다** — 고친 뒤 실행에서는 통과했다.
2026-08-27 dgtour 계획서에도 같은 이름으로 환경 이슈라고 기록돼 있다.

### 알아둘 함정 — 백엔드는 루트 `.env` 를 안 읽는다

처음에 루트 `.env` 만 고쳤더니 **아무 효과가 없었다.**

```python
# backend/app/core/config.py
32  load_env_file(BACKEND_DIR / ".env")
33  load_env_file(BACKEND_DIR / ".env.local", override=True)
```

루트 `.env` 는 docker compose 몫이다. 로컬 pytest 는 `backend/.env` 를 읽고,
그 위를 `backend/.env.local` 이 `override=True` 로 덮는다.
**`.env.local` 이 최종값이다.** 설정을 바꿀 때 여기를 안 고치면 반영되지 않는다.

### 그래서 네 기준선

```
이전   682 passed /  6 failed     ← 포트 5 + 권한 1
지금   688 passed / 8 failed*     ← *8건은 전부 네 Task 3 RED 테스트
```

**이제부터 네 RED 테스트가 아닌 실패가 나오면 그건 진짜 회귀다.**
환경 탓으로 넘기지 마라. Task 8 의 "backend 전체 통과" 게이트도 이제 열릴 수 있다.

### 아직 안 한 것

**실행 중인 백엔드 컨테이너는 여전히 4173 이다.** `.env` 변경은 재기동해야 반영된다.
네가 돌고 있고 5173 서버도 살아 있어서 공유 런타임을 임의로 재기동하지 않았다.
컨테이너 동작(OAuth 리다이렉트, 초대 링크)까지 5173 으로 맞추려면 재기동이 필요하다.

---

## 2. 프런트 기준선도 바뀌었다

네 SDD 원장에 이렇게 적혀 있다.

```
Baseline UI evidence: ... 3 files, 140 tests PASS
```

**이 숫자는 낡았다.** 같은 파일들에 테스트가 추가됐다.

그리고 네가 CHECKLIST 에 "이번 헤더 변경 범위 밖"이라고 적었던 프런트 실패 6건
(`mypage.test.tsx` 5 + `policies.test.tsx` 1) 은 **해결됐다.**

```
이전                307 passed / 6 failed
09-04 09:30 측정    314 passed / 0 failed   (25파일)
09-04 09:35 현재    + backendApi.test.ts 1건 실패 ← 네 Task 4 RED
```

`src/api/backendApi.test.ts::requests one complete sido travel-area catalog` 는
네가 방금 넣은 RED 테스트다. **기준선은 314/0 이고, 그 위의 실패는 네 것이다.**

### 어떻게 고쳤는지 — 픽스처를 바꾼 게 아니다

원인은 `getPolicy` 가 실제 DB 행을 읽고, 거기 실린 `dgtour-영광-8` 이
이후 모든 링크와 스파이 인자로 흘러간 것이었다. 슬러그가 들어오는 지점만 목으로 막았다.

- `mypage.test.tsx` 2·4·5번, `policies.test.tsx` 1번 → `getPolicy` 하나만 목
- `mypage.test.tsx` 1·3번 → 목이 없던 통합 테스트라 인메모리 가짜 저장소(`installExamplePolicyApi`)로
  `getPolicy` / `listPolicies` / `listSavedPolicies` / `savePolicy` / `removeSavedPolicy` 를 하나의 `Set` 위에서 일관되게 굴린다

`listPolicies` 까지 막은 이유가 있다. `PolicyPages.tsx:674` 가 관심 필터를
**전체 목록을 저장 슬러그로 거르는** 방식이라, 찜 상태만 가짜로 만들면 링크가 안 나온다.

**`frontend/src/test/fixtures.ts` 의 `examplePolicySlug = "dgtour-영광"` 은 일부러 그대로 뒀다.**
이게 미병합 `feature/dgtour-canonical-slug` 가 정한 정식 계약이라, 그 가지가 병합되면
DB 도 이 값으로 돌아온다. `-8` 로 바꾸면 그때 또 깨진다. **바꾸지 마라.**

---

## 3. 참고 — 정책 슬러그 문제는 재발이다

로컬 DB 에서 `dgtour-영광` 이 `hidden`, `dgtour-영광-8` 이 `active` 다.
2026-09-03 14:34 정책 수집이 돌면서 바뀌었다.

**같은 문제를 2026-08-27 에 이미 고쳤고 병합되지 않았다.**

```
feature/dgtour-canonical-slug        develop 대비 8커밋 미병합
feature/stabilize-policy-trip-tests  policies.test.tsx 목 처리 포함
```

근본 원인은 크롤러가 `dgtour-{도시}-{페이지순번}` 으로 슬러그를 만드는 것이다
(`backend/scripts/crawl_dgtourcard.py:217`). 조사 문서는 그 브랜치 안에 있다.

```
feature/dgtour-canonical-slug:docs/superpowers/specs/2026-08-27-dgtour-slug-investigation.md
```

이번 범위 밖이지만, **로컬 DB 에 정책 수집을 돌리면 프런트 테스트가 또 흔들린다.** 돌리지 마라.

---

## 4. 네 작업 상태 — 원장이 실제보다 뒤처져 있다

`.superpowers/sdd/2026-09-03-.../progress.md` 에 `Task 2: in progress` 로 남아 있다.
**Task 2 는 사실상 완료다.** 지적됐던 `sourceAsOf` 검증이
`backend/tests/test_travel_area_catalog_routes.py:15` 에 이미 들어가 있다.
서브에이전트가 세션이 끊기기 직전에 반영했고 원장만 못 고쳤다.

09-04 09:33 기준으로 너는 Task 3 GREEN 을 지나 Task 4 에 들어간 것으로 보인다
(`schemas/trip.py`, `services/trips.py`, `itinerary_recommendations.py`, `api/backendApi.test.ts` 수정됨).
**원장을 실제 상태로 갱신해라.**

---

## 5. 곧 부딪힌다 — Task 4~6 이 남의 작업 위에 겹친다

Task 6 은 `ItineraryDetailPage.tsx` 와 `app.css` 를 수정한다.
**두 파일 다 커밋되지 않은 다른 세션의 작업이 들어 있다.**
네 계획 Task 6 Step 1 이 "diff 를 읽고 보존한다"고 적어둔 그 상황이다. 구체적 경계는 이렇다.

### `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`

```
@@ -3513,23 +3749,23 @@     ← 네 것 (히어로 헤더)
그 외 모든 헝크              ← Claude 세션 것
```

Claude 쪽 내용: day 스트립 좌우 끌기(`useDragScroll`), 스트립 버튼을 날짜·장소 수 표시로 교체,
시간 수정 시 시간순 재배치, 장소 수정 시트의 날짜 선택, 드래그 이동영역·충돌 히스테리시스.

### `frontend/src/styles/app.css`

```
7071 ~ 7188    ← 네 것 (일정 상세 헤더)
7504 이후      ← Claude 세션 것
```

7188 과 7504 사이에 헝크가 없어 겹치지 않는다.

### 특히 주의

- `.day-tab` 은 방금 알약(24px)에서 **카드형(74×62px, 날짜+장소 수 3줄)** 으로 바뀌었다.
  `.day-tab.drop-target` 의 `min-width` 는 평소 폭과 **같아야 한다**(현재 74px).
  다르면 드래그 시작 순간 30개 탭이 밀려 가운데 정렬이 어긋난다. 테스트가 이 불변조건을 지킨다.
- `ItineraryCreatePage.tsx` 의 달력 문구 2곳이 한글로 바뀌었다
  (`출발일과 도착일을 고릅니다.`, `완료`). Task 5·6 에서 이 달력을 공통 컴포넌트로 들어낼 때
  **영문으로 되돌리지 마라.** `trip-create.test.tsx` 에 회귀 테스트가 있다
  (달력 안에 3글자 이상 영어 낱말이 없어야 한다).

전체 대조표는 여기 있다.

```
docs/2026-09-04-working-tree-attribution.md
```

다만 그 문서는 09-04 09:00 시점이라 **네 파일 목록은 그 뒤로 더 늘었다.**
Claude 쪽 목록은 그대로 유효하다.

---

## 6. 커밋 규칙과 동시 작업

- **커밋은 아직 아무도 안 했다.** 사용자 지시로 미룬 상태다
- 커밋할 때 `app.css` 와 `ItineraryDetailPage.tsx` 는 파일 단위로 못 가른다.
  `git add -p` 로 위 경계에 맞춰 헝크를 골라야 한다
- 공유 자원은 파일만이 아니다 — DB, 컨테이너, 5173 서버, `.env` 가 전부 하나다.
  실제로 이번에 DB 쪽 변경 때문에 프런트 테스트 6건이 깨졌다
- 다른 세션이 진단 목적으로 `git checkout --` 를 쓴 적이 있다(유실 없음 확인).
  **공유 파일에는 쓰지 않기로 했다.** 너도 쓰지 마라

---

## 7. 요약 — 지금 당장 반영할 것

1. 백엔드 기준선을 `688 passed` 로 갱신. 네 RED 테스트가 아닌 실패는 진짜 회귀다
2. 프런트 기준선을 `314 passed / 0 failed` 로 갱신. 이전 6건은 해결됐다.
   현재 `backendApi.test.ts` 1건 실패는 네 Task 4 RED 다
3. `fixtures.ts` 의 `dgtour-영광` 을 바꾸지 마라
4. 로컬 DB 에 정책 수집을 돌리지 마라
5. 설정을 바꿀 때는 `backend/.env.local` 이 최종값임을 기억해라
6. Task 6 전에 `docs/2026-09-04-working-tree-attribution.md` 의 경계를 읽어라
7. SDD 원장의 Task 2 를 complete 로, 현재 진행을 실제 상태로 고쳐라
